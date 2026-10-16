from src.document_analysis.domain.ocr_layout import OcrFragment, layout_ocr_text


def plain(text: str, x: float, y: float) -> OcrFragment:
    return OcrFragment(text=text, x_center=x, y_center=y, width=12.0 * len(text), height=24.0)


def header(text: str, x: float, length: float = 160.0) -> OcrFragment:
    return OcrFragment(text=text, x_center=x, y_center=0.2, width=28.0, height=length)


HEADERS = [header("Consulta Externa", 0.50), header("Medicina", 0.58), header("Emergencia", 0.66)]


def test_no_fragments_gives_empty_text():
    assert layout_ocr_text([]) == ""


def test_page_without_column_headers_keeps_the_engine_order():
    fragments = [plain("primera línea", 0.1, 0.1), plain("segunda línea", 0.1, 0.2), plain("tercera", 0.1, 0.3)]
    assert layout_ocr_text(fragments) == "primera línea\nsegunda línea\ntercera"


def test_fewer_than_three_rotated_fragments_is_not_a_matrix():
    fragments = [header("Uno", 0.5), header("Dos", 0.6), plain("texto", 0.1, 0.5)]
    assert layout_ocr_text(fragments) == "Uno\nDos\ntexto"


def test_each_mark_is_tied_to_the_column_it_sits_under():
    fragments = [*HEADERS, plain("Enfermería", 0.10, 0.50), plain("X", 0.50, 0.50), plain("X", 0.66, 0.50)]
    lines = layout_ocr_text(fragments).splitlines()
    assert lines[0] == "[Columnas: Consulta Externa | Medicina | Emergencia]"
    assert lines[1] == "Enfermería -> Consulta Externa; Emergencia"


def test_marks_in_different_rows_are_not_mixed():
    fragments = [
        *HEADERS,
        plain("Enfermería", 0.10, 0.50),
        plain("X", 0.58, 0.50),
        plain("Medicina", 0.10, 0.60),
        plain("X", 0.50, 0.60),
    ]
    lines = layout_ocr_text(fragments).splitlines()
    assert "Enfermería -> Medicina" in lines
    assert "Medicina -> Consulta Externa" in lines


def test_fragments_of_one_row_are_joined_in_horizontal_order_despite_small_vertical_noise():
    fragments = [*HEADERS, plain("derecha", 0.30, 0.504), plain("izquierda", 0.10, 0.50)]
    assert "izquierda derecha" in layout_ocr_text(fragments).splitlines()


def test_mark_far_from_every_column_stays_as_plain_text():
    fragments = [*HEADERS, plain("Fila", 0.10, 0.50), plain("X", 0.95, 0.50)]
    assert layout_ocr_text(fragments).splitlines()[1] == "Fila X"


def test_row_without_marks_is_just_its_text():
    fragments = [*HEADERS, plain("Servicio de apoyo", 0.10, 0.50)]
    assert layout_ocr_text(fragments).splitlines()[1] == "Servicio de apoyo"


def test_rows_are_listed_top_to_bottom():
    fragments = [*HEADERS, plain("abajo", 0.1, 0.8), plain("arriba", 0.1, 0.4)]
    assert layout_ocr_text(fragments).splitlines()[1:] == ["arriba", "abajo"]


def test_short_rotated_headers_in_the_same_band_are_recognized_as_columns():
    fragments = [*HEADERS, header("ENF", 0.42, length=48.0), header("UCI", 0.74, length=42.0)]
    fragments += [plain("Fila", 0.10, 0.50), plain("X", 0.42, 0.50), plain("X", 0.74, 0.50)]
    lines = layout_ocr_text(fragments).splitlines()
    assert lines[0] == "[Columnas: ENF | Consulta Externa | Medicina | Emergencia | UCI]"
    assert lines[1] == "Fila -> ENF; UCI"


def test_horizontal_short_text_inside_the_header_band_is_not_a_column():
    fragments = [*HEADERS, plain("SI", 0.80, 0.20), plain("Fila", 0.10, 0.50)]
    assert "SI" not in layout_ocr_text(fragments).splitlines()[0]


def test_short_rotated_text_without_confident_columns_is_left_alone():
    fragments = [header("ENF", 0.42, length=48.0), header("UCI", 0.74, length=42.0), plain("texto", 0.1, 0.5)]
    assert layout_ocr_text(fragments) == "ENF\nUCI\ntexto"


def test_rotated_lines_stacked_at_the_same_horizontal_position_are_not_columns():
    stamp = [OcrFragment(f"Firmado digitalmente {number}", 0.97, 0.2 + number * 0.001, 28.0, 300.0) for number in range(4)]
    fragments = [*stamp, plain("texto del cuerpo", 0.1, 0.5)]
    assert not layout_ocr_text(fragments).startswith("[Columnas")
