import pymupdf
import pytest

from src.document_analysis.domain.models import PageSource
from src.document_analysis.domain.ports import OcrEngine, TextExtractor
from src.document_analysis.infrastructure.extractors.pdf_text_extractor import PdfTextExtractor
from src.shared.enums.error_code import ErrorCode
from src.shared.errors.corrupt_document_error import CorruptDocumentError
from src.shared.errors.document_without_text_error import DocumentWithoutTextError
from src.shared.errors.encrypted_document_error import EncryptedDocumentError

OCR_TEXT = "TEXTO LEIDO POR OCR N° 373"


class FakeOcrEngine:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.received: list[bytes] = []

    def read(self, image_png: bytes) -> str:
        self.received.append(image_png)
        return self.answer


def white_image() -> bytes:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), False)
    pixmap.set_rect(pixmap.irect, (255, 255, 255))
    return pixmap.tobytes("png")


def build_pdf(page_texts: list[str], scanned_pages: tuple[int, ...] = (), encrypt: bool = False) -> bytes:
    document = pymupdf.open()
    for index, text in enumerate(page_texts):
        page = document.new_page()
        if index in scanned_pages:
            page.insert_image(page.rect, stream=white_image())
        if text:
            page.insert_text((72, 72), text)
    options = {"encryption": pymupdf.PDF_ENCRYPT_AES_256, "user_pw": "secret", "owner_pw": "owner"} if encrypt else {}
    return document.tobytes(**options)


def test_extracts_text_page_by_page_with_numbers_starting_at_one():
    document = PdfTextExtractor().extract(build_pdf(["Primera pagina", "Segunda pagina"]), "doc.pdf")
    assert document.name == "doc.pdf"
    assert [page.number for page in document.pages] == [1, 2]
    assert "Primera pagina" in document.pages[0].text
    assert "Segunda pagina" in document.pages[1].text


def test_pages_are_immutable():
    document = PdfTextExtractor().extract(build_pdf(["texto"]), "doc.pdf")
    assert isinstance(document.pages, tuple)


def test_keeps_an_empty_page_between_pages_with_text():
    document = PdfTextExtractor().extract(build_pdf(["uno", "", "tres"]), "doc.pdf")
    assert len(document.pages) == 3
    assert document.pages[1].text.strip() == ""


def test_text_only_pages_are_not_scanned():
    document = PdfTextExtractor().extract(build_pdf(["texto"]), "doc.pdf")
    assert document.pages[0].scanned is False
    assert document.scanned_page_numbers == ()


def test_full_page_image_marks_the_page_as_scanned_without_ocr():
    document = PdfTextExtractor().extract(build_pdf(["capa", "limpia"], scanned_pages=(0,)), "doc.pdf")
    assert document.pages[0].scanned is True
    assert document.pages[0].source == PageSource.TEXT_LAYER
    assert document.pages[0].text.strip() == "capa"
    assert document.scanned_page_numbers == (1,)


def test_ocr_replaces_the_text_layer_only_on_scanned_pages():
    ocr = FakeOcrEngine(OCR_TEXT)
    document = PdfTextExtractor(ocr).extract(build_pdf(["capa mala", "pagina normal"], scanned_pages=(0,)), "doc.pdf")
    assert document.pages[0].text == OCR_TEXT
    assert document.pages[0].source == PageSource.OCR
    assert "pagina normal" in document.pages[1].text
    assert document.pages[1].source == PageSource.TEXT_LAYER
    assert len(ocr.received) == 1
    assert ocr.received[0].startswith(b"\x89PNG")


def test_empty_ocr_answer_falls_back_to_the_text_layer():
    document = PdfTextExtractor(FakeOcrEngine("  ")).extract(build_pdf(["capa buena"], scanned_pages=(0,)), "doc.pdf")
    assert document.pages[0].text.strip() == "capa buena"
    assert document.pages[0].source == PageSource.TEXT_LAYER


def test_scanned_pdf_without_text_layer_is_readable_when_ocr_is_available():
    document = PdfTextExtractor(FakeOcrEngine(OCR_TEXT)).extract(build_pdf([""], scanned_pages=(0,)), "scan.pdf")
    assert document.pages[0].text == OCR_TEXT


def test_pdf_without_any_text_is_rejected_with_422():
    with pytest.raises(DocumentWithoutTextError) as raised:
        PdfTextExtractor().extract(build_pdf(["", ""]), "scan.pdf")
    assert raised.value.status_code == 422
    assert raised.value.error_code == ErrorCode.DOCUMENT_WITHOUT_TEXT
    assert "scan.pdf" not in raised.value.message
    assert raised.value.filename == "scan.pdf"


def test_scanned_pdf_without_text_and_without_ocr_is_rejected():
    with pytest.raises(DocumentWithoutTextError):
        PdfTextExtractor().extract(build_pdf([""], scanned_pages=(0,)), "scan.pdf")


@pytest.mark.parametrize("content", [b"", b"esto no es un pdf"])
def test_corrupt_content_is_rejected_with_422(content: bytes):
    with pytest.raises(CorruptDocumentError) as raised:
        PdfTextExtractor().extract(content, "bad.pdf")
    assert raised.value.status_code == 422
    assert raised.value.error_code == ErrorCode.CORRUPT_DOCUMENT


def test_encrypted_pdf_is_rejected_with_422():
    with pytest.raises(EncryptedDocumentError) as raised:
        PdfTextExtractor().extract(build_pdf(["texto"], encrypt=True), "locked.pdf")
    assert raised.value.status_code == 422
    assert raised.value.error_code == ErrorCode.ENCRYPTED_DOCUMENT


def test_satisfies_the_ports():
    assert isinstance(PdfTextExtractor(), TextExtractor)
    assert isinstance(FakeOcrEngine("x"), OcrEngine)
