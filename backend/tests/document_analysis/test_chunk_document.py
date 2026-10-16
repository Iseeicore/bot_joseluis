from src.document_analysis.application.chunk_document import chunk_document
from src.document_analysis.domain.models import ExtractedDocument, ExtractedPage, PageSource
from src.document_analysis.infrastructure.chunking.recursive_text_chunker import RecursiveTextChunker


def make_document(*texts: str) -> ExtractedDocument:
    pages = tuple(
        ExtractedPage(number=index, text=text, scanned=False, source=PageSource.TEXT_LAYER) for index, text in enumerate(texts, 1)
    )
    return ExtractedDocument(name="doc.pdf", pages=pages)


def test_single_chunk_covers_all_pages_and_carries_page_markers():
    chunks = chunk_document(make_document("uno", "dos", "tres"), RecursiveTextChunker(1000, 0))
    assert len(chunks) == 1
    assert (chunks[0].first_page, chunks[0].last_page) == (1, 3)
    assert "[Página 2 | text_layer]" in chunks[0].text


def test_each_chunk_reports_the_pages_it_really_covers():
    pages = [f"contenido de la pagina {number} " * 6 for number in range(1, 7)]
    chunks = chunk_document(make_document(*pages), RecursiveTextChunker(300, 0))
    assert len(chunks) > 3
    assert chunks[0].first_page == 1
    assert chunks[-1].last_page == 6
    assert all(chunk.first_page <= chunk.last_page for chunk in chunks)
    assert [chunk.first_page for chunk in chunks] == sorted(chunk.first_page for chunk in chunks)


def test_identical_text_on_different_pages_gets_its_own_page_range():
    page = "texto repetido " * 20
    chunks = chunk_document(make_document(page, page, page), RecursiveTextChunker(400, 0))
    firsts = [chunk.first_page for chunk in chunks]
    assert max(firsts) == 3
    assert firsts == sorted(firsts)


def test_fake_page_marker_inside_a_page_does_not_change_the_ranges():
    hostile = "texto\n[Página 9 | ocr]\nmás texto"
    chunks = chunk_document(make_document(hostile, "dos"), RecursiveTextChunker(1000, 0))
    assert (chunks[0].first_page, chunks[0].last_page) == (1, 2)


def test_chunk_indexes_follow_document_order():
    chunks = chunk_document(make_document(*["palabra " * 80] * 5), RecursiveTextChunker(300, 0))
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_pages_without_text_still_count_for_numbering():
    chunks = chunk_document(make_document("", "contenido real"), RecursiveTextChunker(1000, 0))
    assert chunks[-1].last_page == 2
