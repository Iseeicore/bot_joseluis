from dataclasses import dataclass

from src.shared.enums.message_role import MessageRole
from src.shared.enums.page_source import PageSource

__all__ = [
    "ChatMessage",
    "ChunkNote",
    "DocumentAnalysis",
    "DocumentChunk",
    "ExtractedDocument",
    "ExtractedPage",
    "GenerationOptions",
    "PageSource",
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
