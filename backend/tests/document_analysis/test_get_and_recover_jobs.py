import io
import uuid

import pytest

from src.document_analysis.application.get_job import get_job
from src.document_analysis.application.job_idempotency_key import JobIdentity
from src.document_analysis.application.recover_interrupted_jobs import recover_interrupted_jobs
from src.document_analysis.application.submit_job import JobSubmission, SubmitSetup, submit_job
from src.document_analysis.domain.models import GenerationOptions
from src.shared.enums.error_code import ErrorCode
from src.shared.enums.job_status import JobStatus
from src.shared.errors.job_not_found_error import JobNotFoundError
from tests.document_analysis.job_fakes import FIXED_TIMESTAMP, MemoryJobRepository, MemoryUploadStore, fixed_clock

OPTIONS = GenerationOptions(model="m", num_ctx=8192, temperature=0.2, top_p=0.9, keep_alive="1m", max_output_tokens=100, think=False)
IDENTITY = JobIdentity(
    notes_prompt="NOTAS", summary_prompt="RESUMEN", notes_options=OPTIONS, summary_options=OPTIONS, summary_batch_chars=6000
)


@pytest.fixture
def repository() -> MemoryJobRepository:
    return MemoryJobRepository()


def add_job(repository: MemoryJobRepository, status: JobStatus, request: str) -> str:
    setup = SubmitSetup(repository.transaction, MemoryUploadStore(), IDENTITY, fixed_clock, lambda: None)
    job_id = submit_job(JobSubmission(io.BytesIO(b"%PDF"), "ley.pdf", request, False), setup).job_id
    repository.set_status(job_id, status, FIXED_TIMESTAMP)
    return job_id


def test_get_job_returns_the_stored_job(repository: MemoryJobRepository):
    job_id = add_job(repository, JobStatus.QUEUED, "pregunta")
    job = get_job(job_id, repository.transaction)
    assert (job.id, job.status, job.request) == (job_id, JobStatus.QUEUED, "pregunta")


def test_get_job_fails_with_not_found_for_an_unknown_id(repository: MemoryJobRepository):
    missing = str(uuid.uuid4())
    with pytest.raises(JobNotFoundError) as raised:
        get_job(missing, repository.transaction)
    assert raised.value.status_code == 404
    assert raised.value.error_code is ErrorCode.JOB_NOT_FOUND
    assert raised.value.job_id == missing
    assert raised.value.message == "El trabajo solicitado no existe."


def test_recovery_requeues_only_interrupted_jobs(repository: MemoryJobRepository):
    statuses = list(JobStatus)
    job_ids = {status: add_job(repository, status, status.value) for status in statuses}
    assert recover_interrupted_jobs(repository.transaction, fixed_clock) == 3
    final = {status: repository.get_job(job_id).status for status, job_id in job_ids.items()}
    assert final == {
        JobStatus.QUEUED: JobStatus.QUEUED,
        JobStatus.EXTRACTING: JobStatus.QUEUED,
        JobStatus.ANALYZING: JobStatus.QUEUED,
        JobStatus.SUMMARIZING: JobStatus.QUEUED,
        JobStatus.COMPLETED: JobStatus.COMPLETED,
        JobStatus.FAILED: JobStatus.FAILED,
    }


def test_recovery_with_nothing_interrupted_changes_nothing(repository: MemoryJobRepository):
    add_job(repository, JobStatus.COMPLETED, "pregunta")
    assert recover_interrupted_jobs(repository.transaction, fixed_clock) == 0
