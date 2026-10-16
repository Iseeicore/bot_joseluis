from src.document_analysis.domain.ports import Chunker
from src.document_analysis.infrastructure.chunking.recursive_text_chunker import RecursiveTextChunker

PARAGRAPH = "Articulo uno. El establecimiento debe cumplir la norma vigente. " * 4


def test_short_text_stays_in_one_chunk():
    assert RecursiveTextChunker(1000, 100).split("texto corto") == ["texto corto"]


def test_empty_text_gives_no_chunks():
    assert RecursiveTextChunker(1000, 100).split("") == []


def test_no_chunk_exceeds_the_configured_size():
    text = "\n\n".join([PARAGRAPH] * 20)
    chunks = RecursiveTextChunker(500, 50).split(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)


def test_consecutive_chunks_share_context_through_the_overlap():
    text = " ".join(f"palabra{number}" for number in range(400))
    chunks = RecursiveTextChunker(300, 60).split(text)
    shared = set(chunks[0].split()) & set(chunks[1].split())
    assert shared


def test_every_word_survives_the_split():
    words = [f"palabra{number}" for number in range(400)]
    chunks = RecursiveTextChunker(300, 60).split(" ".join(words))
    assert set(words) <= {word for chunk in chunks for word in chunk.split()}


def test_prefers_paragraph_boundaries():
    text = "A" * 200 + "\n\n" + "B" * 200
    assert RecursiveTextChunker(250, 0).split(text) == ["A" * 200, "B" * 200]


def test_satisfies_the_chunker_port():
    assert isinstance(RecursiveTextChunker(1000, 100), Chunker)
