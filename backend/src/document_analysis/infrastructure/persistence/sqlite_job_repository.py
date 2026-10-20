import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from pydantic import BaseModel

from src.document_analysis.domain.models import Job, JobProgress, NewDocumentVersion, NewJob
from src.document_analysis.domain.ports import JobTransaction
from src.document_analysis.infrastructure.persistence.sqlite_database import open_database
from src.shared.enums.job_status import JobStatus
from src.shared.types.error_response import ErrorResponse
from src.shared.types.job_result import JobResult

BEGIN_SQL = "BEGIN IMMEDIATE"
COMMIT_SQL = "COMMIT"
ROLLBACK_SQL = "ROLLBACK"
INSERT_DOCUMENT_SQL = "INSERT INTO documents (id, display_name, created_at) VALUES (?, ?, ?)"
INSERT_VERSION_SQL = (
    "INSERT INTO document_versions (id, document_id, version_number, file_name, file_sha256, file_path, created_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)"
)
FIND_VERSION_SQL = "SELECT id FROM document_versions WHERE file_sha256 = ?"
INSERT_JOB_SQL = (
    "INSERT INTO jobs (id, version_id, request, ocr, idempotency_key, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)
SELECT_JOB_SQL = (
    "SELECT jobs.id, documents.display_name, document_versions.file_name, document_versions.file_path, jobs.request, jobs.ocr, "
    "jobs.status, jobs.progress_done, jobs.progress_total, jobs.result_json, jobs.error_json, jobs.created_at, jobs.updated_at "
    "FROM jobs JOIN document_versions ON document_versions.id = jobs.version_id "
    "JOIN documents ON documents.id = document_versions.document_id "
)
JOB_BY_ID_SQL = SELECT_JOB_SQL + "WHERE jobs.id = ?"
JOB_BY_KEY_SQL = SELECT_JOB_SQL + "WHERE jobs.idempotency_key = ? AND jobs.status <> ?"
OLDEST_JOB_SQL = SELECT_JOB_SQL + "WHERE jobs.status = ? ORDER BY jobs.created_at, jobs.rowid LIMIT 1"
SET_STATUS_SQL = "UPDATE jobs SET status = ?, progress_done = NULL, progress_total = NULL, updated_at = ? WHERE id = ?"
SET_PROGRESS_SQL = "UPDATE jobs SET progress_done = ?, progress_total = ?, updated_at = ? WHERE id = ?"
COMPLETE_JOB_SQL = "UPDATE jobs SET status = ?, result_json = ?, progress_done = NULL, progress_total = NULL, updated_at = ? WHERE id = ?"
FAIL_JOB_SQL = "UPDATE jobs SET status = ?, error_json = ?, progress_done = NULL, progress_total = NULL, updated_at = ? WHERE id = ?"
REQUEUE_JOBS_SQL = (
    "UPDATE jobs SET status = ?, progress_done = NULL, progress_total = NULL, updated_at = ? "
    "WHERE status IN (SELECT value FROM json_each(?))"
)


def parse_optional[Model: BaseModel](model: type[Model], text: str | None) -> Model | None:
    return None if text is None else model.model_validate_json(text)


def to_job(row: sqlite3.Row) -> Job:
    progress = None if row["progress_done"] is None else JobProgress(row["progress_done"], row["progress_total"])
    return Job(
        id=row["id"],
        document_name=row["display_name"],
        file_name=row["file_name"],
        file_path=row["file_path"],
        request=row["request"],
        ocr=bool(row["ocr"]),
        status=JobStatus(row["status"]),
        progress=progress,
        result=parse_optional(JobResult, row["result_json"]),
        error=parse_optional(ErrorResponse, row["error_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqliteJobRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_job(self, sql: str, parameters: tuple[object, ...]) -> Job | None:
        row = self.connection.execute(sql, parameters).fetchone()
        return None if row is None else to_job(row)

    def find_version_id_by_sha(self, file_sha256: str) -> str | None:
        row = self.connection.execute(FIND_VERSION_SQL, (file_sha256,)).fetchone()
        return None if row is None else row["id"]

    def add_document_version(self, version: NewDocumentVersion) -> None:
        self.connection.execute(INSERT_DOCUMENT_SQL, (version.document_id, version.display_name, version.created_at))
        self.connection.execute(
            INSERT_VERSION_SQL,
            (
                version.version_id,
                version.document_id,
                version.version_number,
                version.file_name,
                version.file_sha256,
                version.file_path,
                version.created_at,
            ),
        )

    def find_unfailed_job_by_key(self, idempotency_key: str) -> Job | None:
        return self.find_job(JOB_BY_KEY_SQL, (idempotency_key, JobStatus.FAILED))

    def add_job(self, job: NewJob) -> None:
        self.connection.execute(
            INSERT_JOB_SQL,
            (job.id, job.version_id, job.request, int(job.ocr), job.idempotency_key, job.status, job.created_at, job.created_at),
        )

    def get_job(self, job_id: str) -> Job | None:
        return self.find_job(JOB_BY_ID_SQL, (job_id,))

    def find_oldest_queued_job(self) -> Job | None:
        return self.find_job(OLDEST_JOB_SQL, (JobStatus.QUEUED,))

    def set_status(self, job_id: str, status: JobStatus, timestamp: str) -> None:
        self.connection.execute(SET_STATUS_SQL, (status, timestamp, job_id))

    def set_progress(self, job_id: str, progress: JobProgress, timestamp: str) -> None:
        self.connection.execute(SET_PROGRESS_SQL, (progress.done, progress.total, timestamp, job_id))

    def complete_job(self, job_id: str, result: JobResult, timestamp: str) -> None:
        self.connection.execute(COMPLETE_JOB_SQL, (JobStatus.COMPLETED, result.model_dump_json(by_alias=True), timestamp, job_id))

    def fail_job(self, job_id: str, error: ErrorResponse, timestamp: str) -> None:
        error_json = error.model_dump_json(by_alias=True, exclude_none=True)
        self.connection.execute(FAIL_JOB_SQL, (JobStatus.FAILED, error_json, timestamp, job_id))

    def requeue_jobs(self, statuses: frozenset[JobStatus], timestamp: str) -> int:
        status_list = json.dumps(sorted(status.value for status in statuses))
        return self.connection.execute(REQUEUE_JOBS_SQL, (JobStatus.QUEUED, timestamp, status_list)).rowcount


def open_job_transaction(database_file: Path) -> JobTransaction:
    @contextmanager
    def transaction() -> Iterator[SqliteJobRepository]:
        with closing(open_database(database_file)) as connection:
            connection.isolation_level = None
            connection.row_factory = sqlite3.Row
            connection.execute(BEGIN_SQL)
            try:
                yield SqliteJobRepository(connection)
            except BaseException:
                connection.execute(ROLLBACK_SQL)
                raise
            connection.execute(COMMIT_SQL)

    return transaction
