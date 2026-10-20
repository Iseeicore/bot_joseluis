import io
from dataclasses import replace

import pytest

from src.document_analysis.application.job_idempotency_key import JobIdentity
from src.document_analysis.application.submit_job import JobSubmission, SubmitSetup, submit_job
from src.document_analysis.domain.models import GenerationOptions
from src.shared.enums.job_status import JobStatus
from tests.document_analysis.job_fakes import FIXED_TIMESTAMP, MemoryJobRepository, MemoryUploadStore, fixed_clock

OPTIONS = GenerationOptions(model="m", num_ctx=8192, temperature=0.2, top_p=0.9, keep_alive="1m", max_output_tokens=100, think=False)
IDENTITY = JobIdentity(
    notes_prompt="NOTAS", summary_prompt="RESUMEN", notes_options=OPTIONS, summary_options=OPTIONS, summary_batch_chars=6000
)
PDF_BYTES = b"%PDF-1.7 contenido"


class WakeCounter:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> None:
        self.count += 1


@pytest.fixture
def repository() -> MemoryJobRepository:
    return MemoryJobRepository()


@pytest.fixture
def wake() -> WakeCounter:
    return WakeCounter()


@pytest.fixture
def setup(repository: MemoryJobRepository, wake: WakeCounter) -> SubmitSetup:
    return SubmitSetup(open_jobs=repository.transaction, uploads=MemoryUploadStore(), identity=IDENTITY, now=fixed_clock, wake_worker=wake)


def submission(content: bytes = PDF_BYTES, request: str | None = None, ocr: bool = False, name: str = "ley.pdf") -> JobSubmission:
    return JobSubmission(content=io.BytesIO(content), file_name=name, request=request, ocr=ocr)


def test_first_submission_creates_document_version_and_queued_job(setup: SubmitSetup, repository: MemoryJobRepository, wake: WakeCounter):
    submitted = submit_job(submission(request="  ¿Qué plazo?  "), setup)
    job = repository.get_job(submitted.job_id)
    version = next(iter(repository.versions.values()))
    assert submitted.created is True
    assert submitted.status is JobStatus.QUEUED
    assert job.status is JobStatus.QUEUED
    assert job.request == "¿Qué plazo?"
    assert job.document_name == version.display_name == "ley.pdf"
    assert (version.version_number, version.file_name, version.created_at) == (1, "ley.pdf", FIXED_TIMESTAMP)
    assert job.created_at == FIXED_TIMESTAMP
    assert wake.count == 1


def test_whole_submission_runs_in_one_transaction(setup: SubmitSetup, repository: MemoryJobRepository):
    submit_job(submission(), setup)
    assert repository.transactions == 1


def test_blank_request_is_stored_as_the_default_request(setup: SubmitSetup, repository: MemoryJobRepository):
    submitted = submit_job(submission(request="   "), setup)
    assert repository.get_job(submitted.job_id).request == "Resume el documento"


def test_identical_resubmission_returns_the_existing_job(setup: SubmitSetup, repository: MemoryJobRepository, wake: WakeCounter):
    first = submit_job(submission(request="pregunta"), setup)
    second = submit_job(submission(request=" pregunta ", name="copia.pdf"), setup)
    assert second.job_id == first.job_id
    assert second.created is False
    assert len(repository.jobs) == 1
    assert len(repository.versions) == 1
    assert wake.count == 1


def test_existing_job_is_returned_with_its_current_status(setup: SubmitSetup, repository: MemoryJobRepository):
    first = submit_job(submission(), setup)
    repository.set_status(first.job_id, JobStatus.ANALYZING, FIXED_TIMESTAMP)
    assert submit_job(submission(), setup).status is JobStatus.ANALYZING


@pytest.mark.parametrize("changes", [{"request": "otra pregunta"}, {"ocr": True}])
def test_same_file_with_other_options_creates_a_new_job_on_the_same_version(
    setup: SubmitSetup, repository: MemoryJobRepository, changes: dict
):
    first = submit_job(submission(), setup)
    second = submit_job(submission(**changes), setup)
    assert second.created is True
    assert second.job_id != first.job_id
    assert len(repository.versions) == 1


def test_failed_job_does_not_block_a_resubmission(setup: SubmitSetup, repository: MemoryJobRepository):
    first = submit_job(submission(), setup)
    repository.set_status(first.job_id, JobStatus.FAILED, FIXED_TIMESTAMP)
    second = submit_job(submission(), setup)
    assert second.created is True
    assert second.job_id != first.job_id
    assert len(repository.versions) == 1


def test_different_file_creates_a_new_document(setup: SubmitSetup, repository: MemoryJobRepository):
    submit_job(submission(name="a.pdf"), setup)
    submit_job(submission(content=b"%PDF-1.7 otro", name="b.pdf"), setup)
    versions = list(repository.versions.values())
    assert [version.display_name for version in versions] == ["a.pdf", "b.pdf"]
    assert versions[0].document_id != versions[1].document_id
    assert [version.version_number for version in versions] == [1, 1]


def test_changing_a_prompt_creates_a_new_job(setup: SubmitSetup):
    first = submit_job(submission(), setup)
    second = submit_job(submission(), replace(setup, identity=replace(IDENTITY, notes_prompt="NOTAS v2")))
    assert second.created is True
    assert second.job_id != first.job_id
