import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import BinaryIO

from src.document_analysis.domain.models import Job, JobProgress, NewDocumentVersion, NewJob, StoredUpload
from src.shared.enums.job_status import JobStatus
from src.shared.types.error_response import ErrorResponse
from src.shared.types.job_result import JobResult

FIXED_NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
FIXED_TIMESTAMP = "2026-10-18T12:00:00Z"


def fixed_clock() -> datetime:
    return FIXED_NOW


@dataclass
class StatusChange:
    job_id: str
    status: JobStatus
    progress: JobProgress | None


@dataclass
class MemoryJobRepository:
    versions: dict[str, NewDocumentVersion] = field(default_factory=dict)
    jobs: dict[str, Job] = field(default_factory=dict)
    keys: dict[str, str] = field(default_factory=dict)
    history: list[StatusChange] = field(default_factory=list)
    transactions: int = 0

    @contextmanager
    def transaction(self) -> Iterator["MemoryJobRepository"]:
        self.transactions += 1
        yield self

    def find_version_id_by_sha(self, file_sha256: str) -> str | None:
        return next((version.version_id for version in self.versions.values() if version.file_sha256 == file_sha256), None)

    def add_document_version(self, version: NewDocumentVersion) -> None:
        self.versions[version.version_id] = version

    def find_unfailed_job_by_key(self, idempotency_key: str) -> Job | None:
        matches = [self.jobs[job_id] for job_id, key in self.keys.items() if key == idempotency_key]
        return next((job for job in matches if job.status is not JobStatus.FAILED), None)

    def add_job(self, job: NewJob) -> None:
        version = self.versions[job.version_id]
        self.keys[job.id] = job.idempotency_key
        self.jobs[job.id] = Job(
            id=job.id,
            document_name=version.display_name,
            file_name=version.file_name,
            file_path=version.file_path,
            request=job.request,
            ocr=job.ocr,
            status=job.status,
            progress=None,
            result=None,
            error=None,
            created_at=job.created_at,
            updated_at=job.created_at,
        )

    def get_job(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def find_oldest_queued_job(self) -> Job | None:
        return next((job for job in self.jobs.values() if job.status is JobStatus.QUEUED), None)

    def update(self, job_id: str, timestamp: str, **changes: object) -> None:
        job = replace(self.jobs[job_id], updated_at=timestamp, **changes)
        self.jobs[job_id] = job
        self.history.append(StatusChange(job_id, job.status, job.progress))

    def set_status(self, job_id: str, status: JobStatus, timestamp: str) -> None:
        self.update(job_id, timestamp, status=status, progress=None)

    def set_progress(self, job_id: str, progress: JobProgress, timestamp: str) -> None:
        self.update(job_id, timestamp, progress=progress)

    def complete_job(self, job_id: str, result: JobResult, timestamp: str) -> None:
        self.update(job_id, timestamp, status=JobStatus.COMPLETED, progress=None, result=result)

    def fail_job(self, job_id: str, error: ErrorResponse, timestamp: str) -> None:
        self.update(job_id, timestamp, status=JobStatus.FAILED, progress=None, error=error)

    def requeue_jobs(self, statuses: frozenset[JobStatus], timestamp: str) -> int:
        stuck = [job_id for job_id, job in self.jobs.items() if job.status in statuses]
        for job_id in stuck:
            self.set_status(job_id, JobStatus.QUEUED, timestamp)
        return len(stuck)


class MemoryUploadStore:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def save(self, content: BinaryIO) -> StoredUpload:
        data = content.read()
        sha256 = hashlib.sha256(data).hexdigest()
        file_path = f"{sha256}.pdf"
        self.files[file_path] = data
        return StoredUpload(sha256=sha256, file_path=file_path, size_bytes=len(data))

    def read(self, file_path: str) -> bytes:
        return self.files[file_path]
