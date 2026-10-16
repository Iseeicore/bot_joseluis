from typing import Protocol, runtime_checkable

from src.document_analysis.domain.models import ChatMessage, ChunkNote, ExtractedDocument, GenerationOptions


@runtime_checkable
class TextExtractor(Protocol):
    def extract(self, content: bytes, filename: str) -> ExtractedDocument: ...


@runtime_checkable
class LLMClient(Protocol):
    def generate(self, messages: list[ChatMessage], options: GenerationOptions) -> str: ...


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
