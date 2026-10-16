from src.document_analysis.application.assess_text_quality import assess_text_quality
from src.shared.enums.text_quality import TextQuality

HEALTHY_SENTENCE = (
    "La atención de los pacientes en el establecimiento de salud se realiza según la normativa vigente, "
    "y la información clínica del paciente debe registrarse en la historia clínica electrónica. "
)
CORRUPT_SENTENCE = (
    "La atenci6n de los pacientes en el establecimiento de salud se realiza segun la normativa vigente, "
    "y la informacldn clinica del paciente debe registrarse en la historia clinica electrdnica. "
)
ENGLISH_SENTENCE = (
    "The patient care in the health facility is performed according to the current regulations, "
    "and the clinical information of the patient must be recorded in the electronic medical record. "
)


def test_healthy_spanish_text_is_good():
    report = assess_text_quality([HEALTHY_SENTENCE * 12])
    assert report.verdict == TextQuality.GOOD
    assert report.accents_per_100_letters > 2


def test_spanish_text_that_lost_its_accents_is_suspect():
    report = assess_text_quality([CORRUPT_SENTENCE * 12])
    assert report.verdict == TextQuality.SUSPECT
    assert report.accents_per_100_letters < 1


def test_english_text_without_accents_is_not_flagged():
    assert assess_text_quality([ENGLISH_SENTENCE * 12]).verdict == TextQuality.NOT_ASSESSABLE


def test_short_text_is_not_assessable():
    assert assess_text_quality([HEALTHY_SENTENCE]).verdict == TextQuality.NOT_ASSESSABLE


def test_no_pages_is_not_assessable():
    assert assess_text_quality([]).verdict == TextQuality.NOT_ASSESSABLE


def test_pages_are_assessed_together():
    pages = [CORRUPT_SENTENCE * 3] * 4
    assert assess_text_quality(pages).verdict == TextQuality.SUSPECT


def test_report_counts_letters():
    report = assess_text_quality([HEALTHY_SENTENCE * 12])
    assert report.letters > 1500
