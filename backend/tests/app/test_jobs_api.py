import uuid
from contextlib import closing
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from src.app.job_composition import build_job_use_cases
from src.app.main import create_app
from src.document_analysis.application.analyze_document import AnalysisSetup
from src.document_analysis.application.job_idempotency_key import JobIdentity
from src.document_analysis.application.process_next_job import ProcessSetup, process_next_job
from src.document_analysis.application.summarize_analysis import SummarySetup
from src.document_analysis.domain.models import ChatMessage, Generation, GenerationOptions, JobProgress
from src.document_analysis.infrastructure.chunking.recursive_text_chunker import RecursiveTextChunker
from src.document_analysis.infrastructure.extractors.pdf_text_extractor import PdfTextExtractor
from src.document_analysis.infrastructure.persistence.sqlite_database import open_database
from src.document_analysis.infrastructure.persistence.sqlite_job_repository import open_job_transaction
from src.document_analysis.infrastructure.persistence.sqlite_migrations import apply_migrations
from src.document_analysis.infrastructure.storage.file_upload_store import FileUploadStore
from src.document_analysis.infrastructure.storage.json_notes_store import JsonNotesStore
from src.shared.config.settings import load_settings
from src.shared.constants.config import DEFAULT_CONFIG_FILE, MIGRATIONS_DIR
from src.shared.enums.error_code import ErrorCode
from src.shared.enums.job_status import JobStatus
from src.shared.types.error_response import ErrorResponse
from tests.document_analysis.job_fakes import FIXED_TIMESTAMP, fixed_clock

OPTIONS = GenerationOptions(model="m", num_ctx=8192, temperature=0.2, top_p=0.9, keep_alive="1m", max_output_tokens=100, think=False)
IDENTITY = JobIdentity(
    notes_prompt="NOTAS", summary_prompt="RESUMEN", notes_options=OPTIONS, summary_options=OPTIONS, summary_batch_chars=6000
)
NOTE_ANSWER = "- El articulo 5 fija un plazo de 30 dias"
SUMMARY_ANSWER = "Plazo de 30 días [págs. 1-1]."


class ScriptedLlm:
    def generate(self, messages: list[ChatMessage], options: GenerationOptions) -> Generation:
        text = SUMMARY_ANSWER if messages[0].content == IDENTITY.summary_prompt else NOTE_ANSWER
        return Generation(text=text, truncated=False)


def make_pdf(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    return document.tobytes()


class JobsHarness:
    def __init__(self, tmp_path: Path) -> None:
        database_file = tmp_path / "app.db"
        with closing(open_database(database_file)) as connection:
            apply_migrations(connection, MIGRATIONS_DIR)
        self.open_jobs = open_job_transaction(database_file)
        self.uploads = FileUploadStore(tmp_path / "uploads")
        self.wakes = 0
        use_cases = build_job_use_cases(self.open_jobs, self.uploads, IDENTITY, fixed_clock, self.wake)
        settings = load_settings(DEFAULT_CONFIG_FILE, tmp_path / ".env")
        app = create_app(settings, system_prompt="reglas", now=fixed_clock, job_use_cases=use_cases)
        self.client = TestClient(app, raise_server_exceptions=False)
        self.process_setup = ProcessSetup(
            open_jobs=self.open_jobs,
            uploads=self.uploads,
            text_extractor=PdfTextExtractor(),
            ocr_extractor=PdfTextExtractor(),
            analysis=AnalysisSetup(RecursiveTextChunker(6000, 400), ScriptedLlm(), JsonNotesStore(tmp_path / "notes"), "NOTAS", OPTIONS),
            summary=SummarySetup(ScriptedLlm(), "RESUMEN", OPTIONS, 6000),
            now=fixed_clock,
        )

    def wake(self) -> None:
        self.wakes += 1

    def post(self, content: bytes, request: str | None = None, ocr: bool | None = None, name: str = "ley.pdf"):
        data = {key: value for key, value in (("request", request), ("ocr", ocr)) if value is not None}
        return self.client.post("/jobs", files={"file": (name, content, "application/pdf")}, data=data)


@pytest.fixture
def harness(tmp_path: Path) -> JobsHarness:
    return JobsHarness(tmp_path)


PDF = make_pdf("Articulo 5. El plazo es de 30 dias.")


def test_new_submission_is_accepted_with_a_status_url(harness: JobsHarness):
    response = harness.post(PDF, request="¿Qué plazo?")
    body = response.json()
    assert response.status_code == 202
    assert body == {"jobId": body["jobId"], "status": "queued", "statusUrl": f"/jobs/{body['jobId']}"}
    assert uuid.UUID(body["jobId"])
    assert harness.wakes == 1


def test_identical_resubmission_returns_the_same_job_with_200(harness: JobsHarness):
    first = harness.post(PDF, request="¿Qué plazo?")
    second = harness.post(PDF, request="  ¿Qué plazo?  ", name="otra-copia.pdf")
    assert (first.status_code, second.status_code) == (202, 200)
    assert second.json() == first.json()
    assert harness.wakes == 1


def test_different_request_creates_a_new_job(harness: JobsHarness):
    first = harness.post(PDF, request="¿Qué plazo?")
    second = harness.post(PDF, request="¿Quién firma?")
    assert second.status_code == 202
    assert second.json()["jobId"] != first.json()["jobId"]


def test_ocr_flag_is_part_of_the_job_identity(harness: JobsHarness):
    first = harness.post(PDF)
    second = harness.post(PDF, ocr=True)
    assert second.status_code == 202
    assert second.json()["jobId"] != first.json()["jobId"]


def test_failed_job_can_be_resubmitted_as_a_new_job(harness: JobsHarness):
    first_id = harness.post(PDF).json()["jobId"]
    error = ErrorResponse(status_code=503, error_code=ErrorCode.LLM_UNAVAILABLE, message="caído", timestamp=FIXED_TIMESTAMP, path="/x")
    with harness.open_jobs() as jobs:
        jobs.fail_job(first_id, error, FIXED_TIMESTAMP)
    second = harness.post(PDF)
    assert second.status_code == 202
    assert second.json()["jobId"] != first_id


def test_queued_job_status(harness: JobsHarness):
    job_id = harness.post(PDF, request="¿Qué plazo?").json()["jobId"]
    response = harness.client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json() == {
        "jobId": job_id,
        "documentName": "ley.pdf",
        "status": "queued",
        "progress": None,
        "result": None,
        "error": None,
        "createdAt": FIXED_TIMESTAMP,
        "updatedAt": FIXED_TIMESTAMP,
    }


def test_progress_is_shown_while_analyzing(harness: JobsHarness):
    job_id = harness.post(PDF).json()["jobId"]
    with harness.open_jobs() as jobs:
        jobs.set_status(job_id, JobStatus.ANALYZING, FIXED_TIMESTAMP)
        jobs.set_progress(job_id, JobProgress(2, 7), FIXED_TIMESTAMP)
    assert harness.client.get(f"/jobs/{job_id}").json()["progress"] == {"done": 2, "total": 7}


def test_summarizing_starts_without_the_analyzing_progress_and_then_shows_its_own(harness: JobsHarness):
    job_id = harness.post(PDF).json()["jobId"]
    with harness.open_jobs() as jobs:
        jobs.set_status(job_id, JobStatus.ANALYZING, FIXED_TIMESTAMP)
        jobs.set_progress(job_id, JobProgress(109, 109), FIXED_TIMESTAMP)
        jobs.set_status(job_id, JobStatus.SUMMARIZING, FIXED_TIMESTAMP)
    assert harness.client.get(f"/jobs/{job_id}").json()["progress"] is None
    with harness.open_jobs() as jobs:
        jobs.set_progress(job_id, JobProgress(3, 16), FIXED_TIMESTAMP)
    body = harness.client.get(f"/jobs/{job_id}").json()
    assert (body["status"], body["progress"]) == ("summarizing", {"done": 3, "total": 16})


def test_progress_is_hidden_outside_analyzing_and_summarizing(harness: JobsHarness):
    job_id = harness.post(PDF).json()["jobId"]
    with harness.open_jobs() as jobs:
        jobs.set_status(job_id, JobStatus.EXTRACTING, FIXED_TIMESTAMP)
        jobs.set_progress(job_id, JobProgress(1, 2), FIXED_TIMESTAMP)
    assert harness.client.get(f"/jobs/{job_id}").json()["progress"] is None


def test_completed_job_returns_the_result(harness: JobsHarness):
    job_id = harness.post(PDF, request="¿Qué plazo?").json()["jobId"]
    assert process_next_job(harness.process_setup) is True
    body = harness.client.get(f"/jobs/{job_id}").json()
    assert body["status"] == "completed"
    assert body["progress"] is None
    assert body["error"] is None
    assert body["result"] == {
        "summary": SUMMARY_ANSWER,
        "summaryTruncated": False,
        "notes": [{"index": 0, "firstPage": 1, "lastPage": 1, "text": NOTE_ANSWER, "unverifiedFacts": []}],
        "generatedCount": 1,
        "reusedCount": 0,
        "failedIndexes": [],
        "scannedPages": [],
    }


def test_failed_job_returns_its_error(harness: JobsHarness):
    job_id = harness.post(b"esto no es un pdf").json()["jobId"]
    process_next_job(harness.process_setup)
    body = harness.client.get(f"/jobs/{job_id}").json()
    assert body["status"] == "failed"
    assert body["result"] is None
    assert body["error"]["statusCode"] == 422
    assert body["error"]["errorCode"] == "CORRUPT_DOCUMENT"
    assert body["error"]["path"] == f"/jobs/{job_id}"


def test_unknown_job_is_404(harness: JobsHarness):
    response = harness.client.get(f"/jobs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["errorCode"] == "JOB_NOT_FOUND"


def test_malformed_job_id_is_400(harness: JobsHarness):
    response = harness.client.get("/jobs/no-es-un-uuid")
    assert response.status_code == 400
    assert response.json()["errorCode"] == "VALIDATION_ERROR"


def test_empty_file_is_400(harness: JobsHarness):
    response = harness.post(b"")
    assert response.status_code == 400
    assert response.json()["errorCode"] == "EMPTY_FILE"
    assert harness.wakes == 0


def test_missing_file_is_400(harness: JobsHarness):
    response = harness.client.post("/jobs", data={"request": "pregunta"})
    assert response.status_code == 400
    assert response.json()["errorCode"] == "VALIDATION_ERROR"


def test_invalid_ocr_flag_is_400(harness: JobsHarness):
    response = harness.post(PDF, ocr="quizas")
    assert response.status_code == 400
    assert response.json()["details"][0]["path"] == "body.ocr"
