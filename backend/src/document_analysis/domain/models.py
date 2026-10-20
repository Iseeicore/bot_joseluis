from dataclasses import dataclass

from src.shared.enums.job_status import PROGRESS_JOB_STATUSES, JobStatus
from src.shared.enums.message_role import MessageRole
from src.shared.enums.page_source import PageSource
from src.shared.types.error_response import ErrorResponse
from src.shared.types.job_result import JobResult

__all__ = [
    "ChatMessage",
    "ChunkNote",
    "DocumentAnalysis",
    "DocumentChunk",
    "ExtractedDocument",
    "ExtractedPage",
    "Generation",
    "GenerationOptions",
    "Job",
    "JobProgress",
    "NewDocumentVersion",
    "NewJob",
    "PageSource",
    "StoredUpload",
]


@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True)
class ExtractedPage:
    number: int
    text: str
    scanned: bool
    source: PageSource


@dataclass(frozen=True)
class ExtractedDocument:
    name: str
    pages: tuple[ExtractedPage, ...]

    @property
    def scanned_page_numbers(self) -> tuple[int, ...]:
        return tuple(page.number for page in self.pages if page.scanned)


@dataclass(frozen=True)
class GenerationOptions:
    model: str
    num_ctx: int
    temperature: float
    top_p: float
    keep_alive: str
    max_output_tokens: int
    think: bool


@dataclass(frozen=True)
class Generation:
    text: str
    truncated: bool


@dataclass(frozen=True)
class DocumentChunk:
    index: int
    text: str
    first_page: int
    last_page: int


@dataclass(frozen=True)
class ChunkNote:
    index: int
    first_page: int
    last_page: int
    text: str
    unverified_facts: tuple[str, ...]


@dataclass(frozen=True)
class DocumentAnalysis:
    name: str
    notes: tuple[ChunkNote, ...]
    generated_count: int
    reused_count: int
    failed_indexes: tuple[int, ...] = ()


@dataclass(frozen=True)
class StoredUpload:
    sha256: str
    file_path: str
    size_bytes: int


@dataclass(frozen=True)
class NewDocumentVersion:
    document_id: str
    version_id: str
    display_name: str
    version_number: int
    file_name: str
    file_sha256: str
    file_path: str
    created_at: str


@dataclass(frozen=True)
class NewJob:
    id: str
    version_id: str
    request: str
    ocr: bool
    idempotency_key: str
    status: JobStatus
    created_at: str


@dataclass(frozen=True)
class JobProgress:
    done: int
    total: int


@dataclass(frozen=True)
class Job:
    id: str
    document_name: str
    file_name: str
    file_path: str
    request: str
    ocr: bool
    status: JobStatus
    progress: JobProgress | None
    result: JobResult | None
    error: ErrorResponse | None
    created_at: str
    updated_at: str

    @property
    def visible_progress(self) -> JobProgress | None:
        return self.progress if self.status in PROGRESS_JOB_STATUSES else None
