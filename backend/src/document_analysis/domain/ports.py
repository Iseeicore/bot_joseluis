from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import BinaryIO, Protocol, runtime_checkable

from src.document_analysis.domain.models import (
    ChatMessage,
    ChunkNote,
    ExtractedDocument,
    Generation,
    GenerationOptions,
    Job,
    JobProgress,
    NewDocumentVersion,
    NewJob,
    StoredUpload,
)
from src.shared.enums.job_status import JobStatus
from src.shared.types.error_response import ErrorResponse
from src.shared.types.job_result import JobResult


@runtime_checkable
class TextExtractor(Protocol):
    def extract(self, content: bytes, filename: str) -> ExtractedDocument: ...


@runtime_checkable
class LLMClient(Protocol):
    def generate(self, messages: list[ChatMessage], options: GenerationOptions) -> Generation: ...


@runtime_checkable
class Chunker(Protocol):
    def split(self, text: str) -> list[str]: ...


@runtime_checkable
class OcrEngine(Protocol):
    def read(self, image_png: bytes) -> str: ...


@runtime_checkable
class NotesStore(Protocol):
    def load(self, fingerprint: str) -> ChunkNote | None: ...

    def save(self, fingerprint: str, note: ChunkNote) -> None: ...


@runtime_checkable
class UploadStore(Protocol):
    def save(self, content: BinaryIO) -> StoredUpload: ...

    def read(self, file_path: str) -> bytes: ...


@runtime_checkable
class JobRepository(Protocol):
    def find_version_id_by_sha(self, file_sha256: str) -> str | None: ...

    def add_document_version(self, version: NewDocumentVersion) -> None: ...

    def find_unfailed_job_by_key(self, idempotency_key: str) -> Job | None: ...

    def add_job(self, job: NewJob) -> None: ...

    def get_job(self, job_id: str) -> Job | None: ...

    def find_oldest_queued_job(self) -> Job | None: ...

    def set_status(self, job_id: str, status: JobStatus, timestamp: str) -> None: ...

    def set_progress(self, job_id: str, progress: JobProgress, timestamp: str) -> None: ...

    def complete_job(self, job_id: str, result: JobResult, timestamp: str) -> None: ...

    def fail_job(self, job_id: str, error: ErrorResponse, timestamp: str) -> None: ...

    def requeue_jobs(self, statuses: frozenset[JobStatus], timestamp: str) -> int: ...


JobTransaction = Callable[[], AbstractContextManager[JobRepository]]
