import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

import pytest

from src.document_analysis.domain.models import JobProgress, NewDocumentVersion, NewJob
from src.document_analysis.infrastructure.persistence.sqlite_database import open_database
from src.document_analysis.infrastructure.persistence.sqlite_job_repository import open_job_transaction
from src.document_analysis.infrastructure.persistence.sqlite_migrations import apply_migrations
from src.shared.constants.config import MIGRATIONS_DIR
from src.shared.enums.error_code import ErrorCode
from src.shared.enums.job_status import RUNNING_JOB_STATUSES, JobStatus
from src.shared.types.error_response import ErrorResponse
from src.shared.types.job_result import JobNote, JobResult

CREATED = "2026-10-18T12:00:00Z"
LATER = "2026-10-18T12:05:00Z"
KEY = "k" * 64


@pytest.fixture
def database_file(tmp_path: Path) -> Path:
    path = tmp_path / "data" / "app.db"
    with closing(open_database(path)) as connection:
        apply_migrations(connection, MIGRATIONS_DIR)
    return path


@pytest.fixture
def open_jobs(database_file: Path):
    return open_job_transaction(database_file)


def new_version(sha: str = "a" * 64, name: str = "ley.pdf") -> NewDocumentVersion:
    return NewDocumentVersion(
        document_id=str(uuid.uuid4()),
        version_id=str(uuid.uuid4()),
        display_name=name,
        version_number=1,
        file_name=name,
        file_sha256=sha,
        file_path=f"{sha}.pdf",
        created_at=CREATED,
    )


def new_job(version_id: str, key: str = KEY, created_at: str = CREATED, request: str = "pregunta") -> NewJob:
    return NewJob(
        id=str(uuid.uuid4()),
        version_id=version_id,
        request=request,
        ocr=True,
        idempotency_key=key,
        status=JobStatus.QUEUED,
        created_at=created_at,
    )


def seed(open_jobs, key: str = KEY, created_at: str = CREATED) -> NewJob:
    with open_jobs() as jobs:
        version_id = jobs.find_version_id_by_sha("a" * 64)
        if version_id is None:
            version = new_version()
            jobs.add_document_version(version)
            version_id = version.version_id
        job = new_job(version_id, key, created_at)
        jobs.add_job(job)
    return job


def test_stores_and_reads_a_job_with_its_document(open_jobs):
    version = new_version()
    job = new_job(version.version_id)
    with open_jobs() as jobs:
        jobs.add_document_version(version)
        jobs.add_job(job)
    with open_jobs() as jobs:
        stored = jobs.get_job(job.id)
        assert jobs.find_version_id_by_sha(version.file_sha256) == version.version_id
        assert jobs.find_version_id_by_sha("b" * 64) is None
    assert (stored.id, stored.document_name, stored.file_name, stored.file_path) == (job.id, "ley.pdf", "ley.pdf", version.file_path)
    assert (stored.request, stored.ocr, stored.status, stored.progress) == ("pregunta", True, JobStatus.QUEUED, None)
    assert (stored.result, stored.error, stored.created_at, stored.updated_at) == (None, None, CREATED, CREATED)


def test_unknown_job_is_none(open_jobs):
    with open_jobs() as jobs:
        assert jobs.get_job(str(uuid.uuid4())) is None


def test_failed_transaction_rolls_back_every_write(open_jobs):
    version = new_version()
    with pytest.raises(sqlite3.IntegrityError), open_jobs() as jobs:
        jobs.add_document_version(version)
        jobs.add_job(new_job(str(uuid.uuid4())))
    with open_jobs() as jobs:
        assert jobs.find_version_id_by_sha(version.file_sha256) is None


def test_same_sha256_cannot_be_stored_twice(open_jobs):
    with open_jobs() as jobs:
        jobs.add_document_version(new_version())
    with pytest.raises(sqlite3.IntegrityError), open_jobs() as jobs:
        jobs.add_document_version(new_version())


def test_two_unfailed_jobs_cannot_share_an_idempotency_key(open_jobs):
    seed(open_jobs)
    with pytest.raises(sqlite3.IntegrityError):
        seed(open_jobs)


def test_failed_job_frees_its_idempotency_key(open_jobs):
    first = seed(open_jobs)
    with open_jobs() as jobs:
        assert jobs.find_unfailed_job_by_key(KEY).id == first.id
        jobs.fail_job(first.id, error_for(first.id), LATER)
        assert jobs.find_unfailed_job_by_key(KEY) is None
    second = seed(open_jobs)
    with open_jobs() as jobs:
        assert jobs.find_unfailed_job_by_key(KEY).id == second.id


def test_status_column_accepts_every_job_status_and_nothing_else(open_jobs, database_file: Path):
    job = seed(open_jobs)
    for status in JobStatus:
        with open_jobs() as jobs:
            jobs.set_status(job.id, status, LATER)
            assert jobs.get_job(job.id).status is status
    with closing(sqlite3.connect(database_file)) as connection, pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        connection.execute("UPDATE jobs SET status = 'paused' WHERE id = ?", (job.id,))


def test_oldest_queued_job_is_found_first(open_jobs):
    newest = seed(open_jobs, key="n" * 64, created_at=LATER)
    oldest = seed(open_jobs, key="o" * 64, created_at=CREATED)
    with open_jobs() as jobs:
        assert jobs.find_oldest_queued_job().id == oldest.id
        jobs.set_status(oldest.id, JobStatus.EXTRACTING, LATER)
        assert jobs.find_oldest_queued_job().id == newest.id
        jobs.set_status(newest.id, JobStatus.COMPLETED, LATER)
        assert jobs.find_oldest_queued_job() is None


def test_progress_is_stored_and_cleared_by_the_next_status(open_jobs):
    job = seed(open_jobs)
    with open_jobs() as jobs:
        jobs.set_status(job.id, JobStatus.ANALYZING, LATER)
        jobs.set_progress(job.id, JobProgress(2, 5), LATER)
        assert jobs.get_job(job.id).progress == JobProgress(2, 5)
        jobs.set_status(job.id, JobStatus.SUMMARIZING, LATER)
        stored = jobs.get_job(job.id)
    assert stored.progress is None
    assert stored.updated_at == LATER


def test_completed_job_keeps_its_result(open_jobs):
    job = seed(open_jobs)
    result = JobResult(
        summary="resumen",
        notes=[JobNote(index=0, first_page=1, last_page=2, text="- nota", unverified_facts=["30"])],
        generated_count=1,
        reused_count=0,
        failed_indexes=[],
        scanned_pages=[2],
    )
    with open_jobs() as jobs:
        jobs.complete_job(job.id, result, LATER)
        stored = jobs.get_job(job.id)
    assert (stored.status, stored.result, stored.error) == (JobStatus.COMPLETED, result, None)


def test_result_stored_before_the_truncation_flag_existed_reads_as_not_truncated(open_jobs, database_file: Path):
    job = seed(open_jobs)
    legacy_result = '{"summary": "resumen", "notes": [], "generatedCount": 1, "reusedCount": 0, "failedIndexes": [], "scannedPages": []}'
    with closing(sqlite3.connect(database_file)) as connection, connection:
        connection.execute("UPDATE jobs SET status = 'completed', result_json = ? WHERE id = ?", (legacy_result, job.id))
    with open_jobs() as jobs:
        stored = jobs.get_job(job.id)
    assert (stored.result.summary, stored.result.summary_truncated) == ("resumen", False)


def error_for(job_id: str) -> ErrorResponse:
    return ErrorResponse(status_code=422, error_code=ErrorCode.CORRUPT_DOCUMENT, message="dañado", timestamp=LATER, path=f"/jobs/{job_id}")


def test_failed_job_keeps_its_error(open_jobs):
    job = seed(open_jobs)
    with open_jobs() as jobs:
        jobs.fail_job(job.id, error_for(job.id), LATER)
        stored = jobs.get_job(job.id)
    assert (stored.status, stored.error, stored.result) == (JobStatus.FAILED, error_for(job.id), None)


def test_requeue_moves_only_the_given_statuses_back_to_queued(open_jobs):
    jobs_by_status = {status: seed(open_jobs, key=status.value.ljust(64, "x")) for status in JobStatus}
    with open_jobs() as jobs:
        for status, job in jobs_by_status.items():
            jobs.set_status(job.id, status, CREATED)
        jobs.set_progress(jobs_by_status[JobStatus.ANALYZING].id, JobProgress(1, 4), CREATED)
        assert jobs.requeue_jobs(RUNNING_JOB_STATUSES, LATER) == 3
        final = {status: jobs.get_job(job.id) for status, job in jobs_by_status.items()}
    assert {status: job.status for status, job in final.items()} == {
        JobStatus.QUEUED: JobStatus.QUEUED,
        JobStatus.EXTRACTING: JobStatus.QUEUED,
        JobStatus.ANALYZING: JobStatus.QUEUED,
        JobStatus.SUMMARIZING: JobStatus.QUEUED,
        JobStatus.COMPLETED: JobStatus.COMPLETED,
        JobStatus.FAILED: JobStatus.FAILED,
    }
    assert final[JobStatus.ANALYZING].progress is None
    assert final[JobStatus.ANALYZING].updated_at == LATER
    assert final[JobStatus.COMPLETED].updated_at == CREATED
