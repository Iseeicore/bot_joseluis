import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import BinaryIO

from src.document_analysis.application.job_idempotency_key import JobIdentity, job_idempotency_key, normalize_request
from src.document_analysis.domain.models import NewDocumentVersion, NewJob, StoredUpload
from src.document_analysis.domain.ports import JobRepository, JobTransaction, UploadStore
from src.shared.enums.job_status import JobStatus
from src.shared.types.clock import Clock
from src.shared.utils.format_timestamp import format_timestamp

FIRST_VERSION_NUMBER = 1


@dataclass(frozen=True)
class JobSubmission:
    content: BinaryIO
    file_name: str
    request: str | None
    ocr: bool


@dataclass(frozen=True)
class SubmitSetup:
    open_jobs: JobTransaction
    uploads: UploadStore
    identity: JobIdentity
    now: Clock
    wake_worker: Callable[[], None]


@dataclass(frozen=True)
class SubmittedJob:
    job_id: str
    status: JobStatus
    created: bool


def new_id() -> str:
    return str(uuid.uuid4())


def find_or_create_version(jobs: JobRepository, upload: StoredUpload, file_name: str, timestamp: str) -> str:
    existing = jobs.find_version_id_by_sha(upload.sha256)
    if existing is not None:
        return existing
    version = NewDocumentVersion(
        document_id=new_id(),
        version_id=new_id(),
        display_name=file_name,
        version_number=FIRST_VERSION_NUMBER,
        file_name=file_name,
        file_sha256=upload.sha256,
        file_path=upload.file_path,
        created_at=timestamp,
    )
    jobs.add_document_version(version)
    return version.version_id


def submit_job(submission: JobSubmission, setup: SubmitSetup) -> SubmittedJob:
    upload = setup.uploads.save(submission.content)
    request = normalize_request(submission.request)
    key = job_idempotency_key(upload.sha256, request, submission.ocr, setup.identity)
    timestamp = format_timestamp(setup.now())
    with setup.open_jobs() as jobs:
        version_id = find_or_create_version(jobs, upload, submission.file_name, timestamp)
        existing = jobs.find_unfailed_job_by_key(key)
        if existing is not None:
            return SubmittedJob(job_id=existing.id, status=existing.status, created=False)
        job = NewJob(new_id(), version_id, request, submission.ocr, key, JobStatus.QUEUED, timestamp)
        jobs.add_job(job)
    setup.wake_worker()
    return SubmittedJob(job_id=job.id, status=job.status, created=True)
