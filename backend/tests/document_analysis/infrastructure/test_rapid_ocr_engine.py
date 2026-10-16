import pymupdf

from src.document_analysis.domain.ports import OcrEngine
from src.document_analysis.infrastructure.ocr.rapid_ocr_engine import RapidOcrEngine


def render_text_image(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page(width=420, height=120)
    page.insert_text((20, 70), text, fontsize=28)
    return page.get_pixmap(dpi=150).tobytes("png")


def test_reads_text_from_an_image():
    text = RapidOcrEngine().read(render_text_image("RESOLUCION 373"))
    assert "373" in text
    assert "RESOLUCION" in text.upper()


def test_image_without_text_returns_empty_string():
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 300), False)
    pixmap.set_rect(pixmap.irect, (255, 255, 255))
    assert RapidOcrEngine().read(pixmap.tobytes("png")) == ""


def test_satisfies_the_ocr_port():
    assert isinstance(RapidOcrEngine(), OcrEngine)


def render_matrix_page() -> bytes:
    document = pymupdf.open()
    page = document.new_page(width=600, height=420)
    columns = {"Emergencia": 330, "Medicina": 400, "Cirugia": 470}
    for name, x in columns.items():
        page.insert_text((x, 160), name, fontsize=16, rotate=90)
    rows = {"Enfermeria": ("Emergencia", "Cirugia"), "Laboratorio": ("Medicina",), "Farmacia": ("Emergencia", "Medicina")}
    for index, (label, marks) in enumerate(rows.items()):
        y = 220 + index * 45
        page.insert_text((40, y), label, fontsize=18)
        for mark in marks:
            page.insert_text((columns[mark] - 4, y), "X", fontsize=18)
    return page.get_pixmap(dpi=150).tobytes("png")


def test_marks_are_tied_to_their_rotated_column_headers():
    lines = RapidOcrEngine().read(render_matrix_page()).splitlines()
    assert lines[0].startswith("[Columnas:")
    rows = {line.split(" -> ")[0].strip().lower(): line.split(" -> ")[1] for line in lines if " -> " in line}
    assert "emergencia" in rows["enfermeria"].lower() and "cirugia" in rows["enfermeria"].lower()
    assert rows["laboratorio"].lower().strip() == "medicina"
    assert "emergencia" in rows["farmacia"].lower() and "medicina" in rows["farmacia"].lower()
