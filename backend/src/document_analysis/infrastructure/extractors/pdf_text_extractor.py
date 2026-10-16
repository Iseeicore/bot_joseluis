import pymupdf

from src.document_analysis.domain.models import ExtractedDocument, ExtractedPage
from src.document_analysis.domain.ports import OcrEngine
from src.shared.constants.limits.documents import OCR_RENDER_DPI, SCANNED_PAGE_MIN_COVERAGE
from src.shared.enums.page_source import PageSource
from src.shared.errors.corrupt_document_error import CorruptDocumentError
from src.shared.errors.document_without_text_error import DocumentWithoutTextError
from src.shared.errors.encrypted_document_error import EncryptedDocumentError

PDF_FILE_TYPE = "pdf"
IMAGE_FORMAT = "png"


def open_pdf(content: bytes, filename: str) -> pymupdf.Document:
    try:
        return pymupdf.open(stream=content, filetype=PDF_FILE_TYPE)
    except pymupdf.FileDataError as error:
        raise CorruptDocumentError(filename) from error


def largest_image_coverage(page: pymupdf.Page) -> float:
    page_area = page.rect.width * page.rect.height
    areas = [pymupdf.Rect(info["bbox"]).get_area() for info in page.get_image_info()]
    return max(areas, default=0.0) / page_area


class PdfTextExtractor:
    def __init__(self, ocr_engine: OcrEngine | None = None) -> None:
        self.ocr_engine = ocr_engine

    def extract(self, content: bytes, filename: str) -> ExtractedDocument:
        document = open_pdf(content, filename)
        with document:
            if document.needs_pass:
                raise EncryptedDocumentError(filename)
            pages = tuple(self.read_page(page) for page in document)
        if not any(page.text.strip() for page in pages):
            raise DocumentWithoutTextError(filename)
        return ExtractedDocument(name=filename, pages=pages)

    def read_page(self, page: pymupdf.Page) -> ExtractedPage:
        number = page.number + 1
        scanned = largest_image_coverage(page) >= SCANNED_PAGE_MIN_COVERAGE
        ocr_text = self.read_with_ocr(page) if scanned else ""
        if ocr_text:
            return ExtractedPage(number=number, text=ocr_text, scanned=scanned, source=PageSource.OCR)
        return ExtractedPage(number=number, text=page.get_text(), scanned=scanned, source=PageSource.TEXT_LAYER)

    def read_with_ocr(self, page: pymupdf.Page) -> str:
        if self.ocr_engine is None:
            return ""
        image = page.get_pixmap(dpi=OCR_RENDER_DPI).tobytes(IMAGE_FORMAT)
        return self.ocr_engine.read(image).strip()
