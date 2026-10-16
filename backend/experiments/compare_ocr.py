import re
import sys
import time
from pathlib import Path

from src.document_analysis.infrastructure.extractors.pdf_text_extractor import PdfTextExtractor
from src.document_analysis.infrastructure.ocr.rapid_ocr_engine import RapidOcrEngine

WORD_PATTERN = re.compile(r"[a-záéíóúñü0-9]{3,}")
NUMBER_PATTERN = re.compile(r"\b\d{2,}\b")


def vocabulary(text: str, pattern: re.Pattern) -> set[str]:
    return set(pattern.findall(text.lower()))


def render(document) -> str:
    return "\n\n".join(f"[Página {page.number} | {page.source}]\n{page.text}" for page in document.pages)


def main(pdf: Path, output_dir: Path) -> None:
    content = pdf.read_bytes()
    layer = PdfTextExtractor().extract(content, pdf.name)
    started = time.perf_counter()
    ocr = PdfTextExtractor(RapidOcrEngine()).extract(content, pdf.name)
    seconds = time.perf_counter() - started
    layer_text, ocr_text = render(layer), render(ocr)
    (output_dir / f"{pdf.stem}-layer.txt").write_text(layer_text, encoding="utf-8")
    (output_dir / f"{pdf.stem}-ocr.txt").write_text(ocr_text, encoding="utf-8")
    layer_words, ocr_words = vocabulary(layer_text, WORD_PATTERN), vocabulary(ocr_text, WORD_PATTERN)
    layer_numbers, ocr_numbers = vocabulary(layer_text, NUMBER_PATTERN), vocabulary(ocr_text, NUMBER_PATTERN)
    print(
        f"paginas: {len(ocr.pages)} | escaneadas: {len(ocr.scanned_page_numbers)} | leidas por OCR: {sum(p.source == 'ocr' for p in ocr.pages)}"
    )
    print(f"caracteres capa de texto: {sum(len(p.text) for p in layer.pages)}")
    print(f"caracteres OCR:           {sum(len(p.text) for p in ocr.pages)}")
    print(f"tiempo OCR: {seconds:.0f}s ({seconds / len(ocr.pages):.1f}s por pagina)")
    print(f"palabras distintas capa: {len(layer_words)} | OCR: {len(ocr_words)} | en comun: {len(layer_words & ocr_words)}")
    print(f"numeros (2+ digitos) capa: {len(layer_numbers)} | OCR: {len(ocr_numbers)} | en comun: {len(layer_numbers & ocr_numbers)}")
    print(
        f"palabras con tilde o ñ -> capa: {sum(bool(re.search('[áéíóúñ]', w)) for w in layer_words)} | OCR: {sum(bool(re.search('[áéíóúñ]', w)) for w in ocr_words)}"
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
