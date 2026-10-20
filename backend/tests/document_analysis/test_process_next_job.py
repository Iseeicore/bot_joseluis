import io
import logging

import pytest

from src.document_analysis.application.analyze_document import AnalysisSetup
from src.document_analysis.application.job_idempotency_key import JobIdentity
from src.document_analysis.application.process_next_job import ProcessSetup, process_next_job
from src.document_analysis.application.submit_job import JobSubmission, SubmitSetup, submit_job
from src.document_analysis.application.summarize_analysis import SummarySetup
from src.document_analysis.domain.models import (
    ChatMessage,
    ChunkNote,
    ExtractedDocument,
    ExtractedPage,
    Generation,
    GenerationOptions,
    JobProgress,
    PageSource,
)
from src.document_analysis.infrastructure.chunking.recursive_text_chunker import RecursiveTextChunker
from src.shared.enums.error_code import ErrorCode
from src.shared.enums.job_status import JobStatus
from src.shared.errors.corrupt_document_error import CorruptDocumentError
from src.shared.errors.llm_unavailable_error import LlmUnavailableError
from tests.document_analysis.job_fakes import FIXED_TIMESTAMP, MemoryJobRepository, MemoryUploadStore, fixed_clock

OPTIONS = GenerationOptions(model="m", num_ctx=8192, temperature=0.2, top_p=0.9, keep_alive="1m", max_output_tokens=100, think=False)
NOTES_PROMPT = "REGLAS DE NOTAS"
SUMMARY_PROMPT = "REGLAS DE RESUMEN"
IDENTITY = JobIdentity(
    notes_prompt=NOTES_PROMPT, summary_prompt=SUMMARY_PROMPT, notes_options=OPTIONS, summary_options=OPTIONS, summary_batch_chars=6000
)
NOTE_ANSWER = "- La norma fija un plazo de 30 dias habiles"
SUMMARY_ANSWER = "El plazo es de 30 días hábiles [págs. 1-3]."
PAGES = ["".join(f"pagina {number} oracion {line} con plazo de 30 dias. " for line in range(12)) for number in range(1, 4)]


class ScriptedLlm:
    def __init__(self, error: Exception | None = None, summary_truncated: bool = False) -> None:
        self.error = error
        self.summary_truncated = summary_truncated
        self.calls: list[list[ChatMessage]] = []

    def generate(self, messages: list[ChatMessage], options: GenerationOptions) -> Generation:
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        if messages[0].content == SUMMARY_PROMPT:
            return Generation(text=SUMMARY_ANSWER, truncated=self.summary_truncated)
        return Generation(text=NOTE_ANSWER, truncated=False)


class FakeExtractor:
    def __init__(self, scanned: bool = False, error: Exception | None = None) -> None:
        self.scanned = scanned
        self.error = error
        self.calls: list[tuple[bytes, str]] = []

    def extract(self, content: bytes, filename: str) -> ExtractedDocument:
        self.calls.append((content, filename))
        if self.error is not None:
            raise self.error
        pages = tuple(
            ExtractedPage(number=number, text=text, scanned=self.scanned and number == 2, source=PageSource.TEXT_LAYER)
            for number, text in enumerate(PAGES, 1)
        )
        return ExtractedDocument(name=filename, pages=pages)


class MemoryNotes:
    def __init__(self) -> None:
        self.notes: dict[str, ChunkNote] = {}

    def load(self, fingerprint: str) -> ChunkNote | None:
        return self.notes.get(fingerprint)

    def save(self, fingerprint: str, note: ChunkNote) -> None:
        self.notes[fingerprint] = note


class Harness:
    def __init__(self, llm: ScriptedLlm | None = None, text: FakeExtractor | None = None, ocr: FakeExtractor | None = None) -> None:
        self.repository = MemoryJobRepository()
        self.uploads = MemoryUploadStore()
        self.llm = llm or ScriptedLlm()
        self.text_extractor = text or FakeExtractor()
        self.ocr_extractor = ocr or FakeExtractor(scanned=True)
        self.setup = ProcessSetup(
            open_jobs=self.repository.transaction,
            uploads=self.uploads,
            text_extractor=self.text_extractor,
            ocr_extractor=self.ocr_extractor,
            analysis=AnalysisSetup(RecursiveTextChunker(300, 0), self.llm, MemoryNotes(), NOTES_PROMPT, OPTIONS),
            summary=SummarySetup(self.llm, SUMMARY_PROMPT, OPTIONS, 6000),
            now=fixed_clock,
        )

    def submit(self, content: bytes = b"%PDF-1.7 a", request: str | None = "¿Qué plazo fija?", ocr: bool = False) -> str:
        setup = SubmitSetup(self.repository.transaction, self.uploads, IDENTITY, fixed_clock, lambda: None)
        return submit_job(JobSubmission(io.BytesIO(content), "ley.pdf", request, ocr), setup).job_id


def test_empty_queue_processes_nothing():
    harness = Harness()
    assert process_next_job(harness.setup) is False
    assert harness.llm.calls == []


def test_completed_job_stores_the_summary_and_notes_from_the_model():
    harness = Harness()
    job_id = harness.submit()
    assert process_next_job(harness.setup) is True
    job = harness.repository.get_job(job_id)
    assert job.status is JobStatus.COMPLETED
    assert job.error is None
    assert job.result.summary == SUMMARY_ANSWER
    assert job.result.summary_truncated is False
    assert len(job.result.notes) == job.result.generated_count > 1
    assert job.result.notes[0].text == NOTE_ANSWER
    assert job.result.notes[0].first_page == 1
    assert job.result.notes[-1].last_page == 3
    assert job.result.reused_count == 0
    assert job.result.failed_indexes == []
    assert job.result.scanned_pages == []
    assert job.updated_at == FIXED_TIMESTAMP


def test_result_serializes_with_camel_case_keys():
    harness = Harness()
    job_id = harness.submit()
    process_next_job(harness.setup)
    body = harness.repository.get_job(job_id).result.model_dump(by_alias=True)
    assert set(body) == {"summary", "summaryTruncated", "notes", "generatedCount", "reusedCount", "failedIndexes", "scannedPages"}
    assert set(body["notes"][0]) == {"index", "firstPage", "lastPage", "text", "unverifiedFacts"}


def test_truncated_final_answer_is_flagged_on_the_result():
    harness = Harness(llm=ScriptedLlm(summary_truncated=True))
    job_id = harness.submit()
    process_next_job(harness.setup)
    job = harness.repository.get_job(job_id)
    assert job.status is JobStatus.COMPLETED
    assert (job.result.summary, job.result.summary_truncated) == (SUMMARY_ANSWER, True)


def test_job_walks_through_every_status_and_reports_progress_while_analyzing_and_summarizing():
    harness = Harness()
    job_id = harness.submit()
    process_next_job(harness.setup)
    changes = [(change.status, change.progress) for change in harness.repository.history if change.job_id == job_id]
    statuses = [status for status, _ in changes]
    assert statuses[0] is JobStatus.EXTRACTING
    assert statuses[-2:] == [JobStatus.SUMMARIZING, JobStatus.COMPLETED]
    analyzing = [progress for status, progress in changes if status is JobStatus.ANALYZING and progress is not None]
    total = len(harness.repository.get_job(job_id).result.notes)
    assert analyzing == [JobProgress(done, total) for done in range(1, total + 1)]
    summarizing = [progress for status, progress in changes if status is JobStatus.SUMMARIZING]
    assert summarizing == [None, JobProgress(1, 1)]
    assert [progress for status, progress in changes if status not in {JobStatus.ANALYZING, JobStatus.SUMMARIZING}] == [None] * 2


def test_summary_uses_the_request_stored_with_the_job():
    harness = Harness()
    harness.submit(request="  ¿Cuál es la sanción?  ")
    process_next_job(harness.setup)
    summary_call = next(call for call in harness.llm.calls if call[0].content == SUMMARY_PROMPT)
    assert "<solicitud>\n¿Cuál es la sanción?\n</solicitud>" in summary_call[1].content


def test_extracts_the_stored_upload_with_the_text_extractor_by_default():
    harness = Harness()
    harness.submit(content=b"%PDF-1.7 bytes guardados")
    process_next_job(harness.setup)
    assert harness.text_extractor.calls == [(b"%PDF-1.7 bytes guardados", "ley.pdf")]
    assert harness.ocr_extractor.calls == []


def test_ocr_job_uses_the_ocr_extractor_and_reports_scanned_pages():
    harness = Harness()
    job_id = harness.submit(ocr=True)
    process_next_job(harness.setup)
    assert len(harness.ocr_extractor.calls) == 1
    assert harness.text_extractor.calls == []
    assert harness.repository.get_job(job_id).result.scanned_pages == [2]


def test_processes_the_oldest_queued_job_first():
    harness = Harness()
    first = harness.submit(request="primera")
    second = harness.submit(request="segunda")
    process_next_job(harness.setup)
    assert harness.repository.get_job(first).status is JobStatus.COMPLETED
    assert harness.repository.get_job(second).status is JobStatus.QUEUED
    assert process_next_job(harness.setup) is True
    assert harness.repository.get_job(second).status is JobStatus.COMPLETED


def test_app_error_marks_the_job_failed_with_the_api_error_shape():
    harness = Harness(text=FakeExtractor(error=CorruptDocumentError("ley.pdf")))
    job_id = harness.submit()
    assert process_next_job(harness.setup) is True
    job = harness.repository.get_job(job_id)
    assert job.status is JobStatus.FAILED
    assert job.result is None
    assert job.error.model_dump(by_alias=True, exclude_none=True) == {
        "success": False,
        "statusCode": 422,
        "errorCode": "CORRUPT_DOCUMENT",
        "message": "El archivo está dañado o no es un documento válido.",
        "timestamp": FIXED_TIMESTAMP,
        "path": f"/jobs/{job_id}",
    }


def test_unavailable_model_marks_the_job_failed():
    harness = Harness(llm=ScriptedLlm(error=LlmUnavailableError("m")))
    job_id = harness.submit()
    process_next_job(harness.setup)
    job = harness.repository.get_job(job_id)
    assert job.status is JobStatus.FAILED
    assert (job.error.status_code, job.error.error_code) == (503, ErrorCode.LLM_UNAVAILABLE)


def test_unexpected_error_is_logged_and_stored_as_a_generic_internal_error(caplog: pytest.LogCaptureFixture):
    harness = Harness(text=FakeExtractor(error=ZeroDivisionError("secret internal detail")))
    job_id = harness.submit()
    with caplog.at_level(logging.ERROR):
        assert process_next_job(harness.setup) is True
    job = harness.repository.get_job(job_id)
    assert job.status is JobStatus.FAILED
    assert (job.error.status_code, job.error.error_code) == (500, ErrorCode.INTERNAL_ERROR)
    assert job.error.message == "Error interno del servidor."
    assert "secret" not in job.error.model_dump_json()
    assert job_id in caplog.text
    assert "secret internal detail" in caplog.text
