from src.document_analysis.domain.models import DocumentChunk, ExtractedDocument
from src.document_analysis.domain.paged_text import PagedText
from src.document_analysis.domain.ports import Chunker
from src.shared.constants.prompts.analysis import page_marker_text

PAGE_SEPARATOR = "\n"


def build_paged_text(document: ExtractedDocument) -> PagedText:
    parts: list[str] = []
    starts: list[int] = []
    offset = 0
    for page in document.pages:
        part = f"{page_marker_text(page.number, page.source)}\n{page.text}"
        starts.append(offset)
        parts.append(part)
        offset += len(part) + len(PAGE_SEPARATOR)
    return PagedText(
        text=PAGE_SEPARATOR.join(parts),
        page_starts=tuple(starts),
        page_numbers=tuple(page.number for page in document.pages),
    )


def chunk_document(document: ExtractedDocument, chunker: Chunker) -> list[DocumentChunk]:
    paged = build_paged_text(document)
    chunks: list[DocumentChunk] = []
    cursor = 0
    for index, text in enumerate(chunker.split(paged.text)):
        found = paged.text.find(text, cursor)
        start = cursor if found < 0 else found
        end = start + len(text)
        chunks.append(DocumentChunk(index, text, paged.page_at(start), paged.page_at(max(end - 1, start))))
        cursor = start + 1
    return chunks
