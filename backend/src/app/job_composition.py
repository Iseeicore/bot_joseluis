from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from ollama import Client

from src.app.generation_options import to_generation_options
from src.app.job_worker import JobWorker
from src.document_analysis.api.job_dependencies import JobUseCases
from src.document_analysis.application.analyze_document import AnalysisSetup
from src.document_analysis.application.get_job import get_job
from src.document_analysis.application.job_idempotency_key import JobIdentity
from src.document_analysis.application.process_next_job import ProcessSetup, process_next_job
from src.document_analysis.application.recover_interrupted_jobs import recover_interrupted_jobs
from src.document_analysis.application.submit_job import SubmitSetup, submit_job
from src.document_analysis.application.summarize_analysis import SummarySetup
from src.document_analysis.domain.ports import JobTransaction, UploadStore
from src.document_analysis.infrastructure.chunking.recursive_text_chunker import RecursiveTextChunker
from src.document_analysis.infrastructure.extractors.pdf_text_extractor import PdfTextExtractor
from src.document_analysis.infrastructure.llm.ollama_llm_client import OllamaLlmClient
from src.document_analysis.infrastructure.ocr.rapid_ocr_engine import RapidOcrEngine
from src.document_analysis.infrastructure.persistence.sqlite_job_repository import open_job_transaction
from src.document_analysis.infrastructure.storage.file_upload_store import FileUploadStore
from src.document_analysis.infrastructure.storage.json_notes_store import JsonNotesStore
from src.shared.config.settings import Settings
from src.shared.config.system_prompt import load_prompt_file
from src.shared.types.clock import Clock


@dataclass(frozen=True)
class JobRuntime:
    use_cases: JobUseCases
    recover: Callable[[], int]
    worker: JobWorker


def build_job_use_cases(
    open_jobs: JobTransaction, uploads: UploadStore, identity: JobIdentity, now: Clock, wake_worker: Callable[[], None]
) -> JobUseCases:
    setup = SubmitSetup(open_jobs=open_jobs, uploads=uploads, identity=identity, now=now, wake_worker=wake_worker)
    return JobUseCases(submit=partial(submit_job, setup=setup), get=partial(get_job, open_jobs=open_jobs))


def build_process_setup(
    settings: Settings, open_jobs: JobTransaction, uploads: UploadStore, identity: JobIdentity, now: Clock
) -> ProcessSetup:
    llm = OllamaLlmClient(Client(host=settings.ollama.base_url, timeout=settings.ollama.timeout_seconds))
    chunker = RecursiveTextChunker(settings.active.chunk_size_chars, settings.active.chunk_overlap_chars)
    notes_store = JsonNotesStore(settings.notes_dir_path)
    return ProcessSetup(
        open_jobs=open_jobs,
        uploads=uploads,
        text_extractor=PdfTextExtractor(),
        ocr_extractor=PdfTextExtractor(RapidOcrEngine()),
        analysis=AnalysisSetup(chunker, llm, notes_store, identity.notes_prompt, identity.notes_options),
        summary=SummarySetup(llm, identity.summary_prompt, identity.summary_options, identity.summary_batch_chars),
        now=now,
    )


def build_job_identity(settings: Settings) -> JobIdentity:
    return JobIdentity(
        notes_prompt=load_prompt_file(settings.notes_prompt_path),
        summary_prompt=load_prompt_file(settings.summary_prompt_path),
        notes_options=to_generation_options(settings.active),
        summary_options=to_generation_options(settings.summary),
        summary_batch_chars=settings.summary.summary_batch_chars,
    )


def build_job_runtime(settings: Settings, now: Clock) -> JobRuntime:
    open_jobs = open_job_transaction(settings.database_file_path)
    uploads = FileUploadStore(settings.uploads_dir_path)
    identity = build_job_identity(settings)
    worker = JobWorker(partial(process_next_job, build_process_setup(settings, open_jobs, uploads, identity, now)))
    return JobRuntime(
        use_cases=build_job_use_cases(open_jobs, uploads, identity, now, worker.wake),
        recover=partial(recover_interrupted_jobs, open_jobs, now),
        worker=worker,
    )
