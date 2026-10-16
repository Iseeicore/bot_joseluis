from src.document_analysis.application.verify_note_facts import find_unverified_facts

CHUNK = """[Página 56 | ocr]
NO.GBL.009 Cuando se realice el intercambio de información de la HCE
Fecha de prescripción 20181226 Duración 5 días
REPRESENTANTE LEGAL
CORREO ELECTRÓNICO
Resolución N° 373-2025
"""


def test_facts_present_in_the_chunk_are_verified():
    note = "- NO.GBL.009: intercambio de información\n- Fecha de prescripción: 20181226\n- Resolución 373-2025"
    assert find_unverified_facts(note, CHUNK) == ()


def test_invented_name_in_capitals_is_flagged():
    assert find_unverified_facts("- REPRESENTANTE LEGAL: J. PEREZ", CHUNK) == ("PEREZ",)


def test_invented_code_or_figure_is_flagged():
    note = "- Código NO.GBL.099\n- Plazo de 30 días\n- Resolución 373-2025"
    assert find_unverified_facts(note, CHUNK) == ("NO.GBL.099", "30")


def test_ocr_spacing_and_accents_do_not_cause_false_alarms():
    chunk = "Fecha 2018 12 26 y CORREO ELECTRONICO"
    assert find_unverified_facts("- 20181226 CORREO ELECTRÓNICO", chunk) == ()


def test_note_without_facts_has_nothing_to_flag():
    assert find_unverified_facts("- Sin contenido relevante", CHUNK) == ()


def test_repeated_invented_fact_is_reported_once_in_order():
    note = "- PEREZ firmó 99\n- PEREZ y 99 y 77"
    assert find_unverified_facts(note, CHUNK) == ("PEREZ", "99", "77")


def test_single_digit_list_numbering_is_ignored():
    assert find_unverified_facts("1. algo\n2. otro", CHUNK) == ()
