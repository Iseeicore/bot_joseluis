import logging
from dataclasses import dataclass
from http import HTTPStatus

from src.document_analysis.application.analyze_document import AnalysisSetup, analyze_document
from src.document_analysis.application.progress import ProgressCallback
from src.document_analysis.application.summarize_analysis import SummarySetup, summarize_analysis
from src.document_analysis.domain.models import DocumentAnalysis, ExtractedDocument, Generation, Job, JobProgress
from src.document_analysis.domain.ports import JobTransaction, TextExtractor, UploadStore
from src.shared.constants.routes import job_status_path
from src.shared.constants.texts.errors import INTERNAL_ERROR_TEXT
from src.shared.enums.error_code import ErrorCode
from src.shared.enums.job_status import JobStatus
from src.shared.errors.app_error import AppError
from src.shared.types.clock import Clock
from src.shared.types.error_response import ErrorResponse
from src.shared.types.job_result import JobNote, JobResult
from src.shared.utils.format_timestamp import format_timestamp

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessSetup:
    open_jobs: JobTransaction
    uploads: UploadStore
    text_extractor: TextExtractor
    ocr_extractor: TextExtractor
    analysis: AnalysisSetup
    summary: SummarySetup
    now: Clock


def claim_next_job(setup: ProcessSetup) -> Job | None:
    with setup.open_jobs() as jobs:
        job = jobs.find_oldest_queued_job()
        if job is not None:
            jobs.set_status(job.id, JobStatus.EXTRACTING, format_timestamp(setup.now()))
    return job


def change_status(job_id: str, status: JobStatus, setup: ProcessSetup) -> None:
    with setup.open_jobs() as jobs:
        jobs.set_status(job_id, status, format_timestamp(setup.now()))


def progress_recorder(job_id: str, setup: ProcessSetup) -> ProgressCallback:
    def record(done: int, total: int) -> None:
        with setup.open_jobs() as jobs:
            jobs.set_progress(job_id, JobProgress(done, total), format_timestamp(setup.now()))

    return record


def to_job_result(analysis: DocumentAnalysis, summary: Generation, document: ExtractedDocument) -> JobResult:
    notes = [
        JobNote(
            index=note.index,
            first_page=note.first_page,
            last_page=note.last_page,
            text=note.text,
            unverified_facts=list(note.unverified_facts),
        )
        for note in analysis.notes
    ]
    return JobResult(
        summary=summary.text,
        summary_truncated=summary.truncated,
        notes=notes,
        generated_count=analysis.generated_count,
        reused_count=analysis.reused_count,
        failed_indexes=list(analysis.failed_indexes),
        scanned_pages=list(document.scanned_page_numbers),
    )


def run_job(job: Job, setup: ProcessSetup) -> JobResult:
    extractor = setup.ocr_extractor if job.ocr else setup.text_extractor
    document = extractor.extract(setup.uploads.read(job.file_path), job.file_name)
    change_status(job.id, JobStatus.ANALYZING, setup)
    analysis = analyze_document(document, setup.analysis, progress_recorder(job.id, setup))
    change_status(job.id, JobStatus.SUMMARIZING, setup)
    summary = summarize_analysis(analysis, job.request, setup.summary, progress_recorder(job.id, setup))
    return to_job_result(analysis, summary, document)


def job_error(job_id: str, status_code: int, error_code: ErrorCode, message: str, setup: ProcessSetup) -> ErrorResponse:
    return ErrorResponse(
        status_code=status_code,
        error_code=error_code,
        message=message,
        timestamp=format_timestamp(setup.now()),
        path=job_status_path(job_id),
    )


def fail_job(job_id: str, error: ErrorResponse, setup: ProcessSetup) -> None:
    with setup.open_jobs() as jobs:
        jobs.fail_job(job_id, error, error.timestamp)


def complete_job(job_id: str, result: JobResult, setup: ProcessSetup) -> None:
    with setup.open_jobs() as jobs:
        jobs.complete_job(job_id, result, format_timestamp(setup.now()))


def process_next_job(setup: ProcessSetup) -> bool:
    job = claim_next_job(setup)
    if job is None:
        return False
    try:
        result = run_job(job, setup)
    except AppError as error:
        logger.warning("Job %s failed with %s", job.id, error.error_code)
        fail_job(job.id, job_error(job.id, error.status_code, error.error_code, error.message, setup), setup)
    except Exception:
        logger.exception("Job %s failed with an unexpected error", job.id)
        internal = job_error(job.id, HTTPStatus.INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR, INTERNAL_ERROR_TEXT, setup)
        fail_job(job.id, internal, setup)
    else:
        complete_job(job.id, result, setup)
    return True
