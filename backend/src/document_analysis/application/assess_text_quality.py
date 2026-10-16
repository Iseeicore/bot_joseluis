from collections.abc import Sequence

from src.document_analysis.domain.text_quality_report import TextQualityReport
from src.shared.constants.limits.text_quality import (
    LETTERS_BASE,
    MIN_ACCENTS_PER_100_LETTERS,
    MIN_LETTERS_FOR_ASSESSMENT,
    MIN_SPANISH_STOPWORD_SHARE,
    SPANISH_STOPWORDS,
)
from src.shared.constants.regex.text_quality import ACCENT_PATTERN, LETTER_PATTERN, WORD_PATTERN
from src.shared.enums.text_quality import TextQuality


def stopword_share(text: str) -> float:
    words = [word.lower() for word in WORD_PATTERN.findall(text)]
    if not words:
        return 0.0
    return sum(word in SPANISH_STOPWORDS for word in words) / len(words)


def assess_text_quality(texts: Sequence[str]) -> TextQualityReport:
    text = "\n".join(texts)
    letters = len(LETTER_PATTERN.findall(text))
    accents_per_100 = LETTERS_BASE * len(ACCENT_PATTERN.findall(text)) / letters if letters else 0.0
    if letters < MIN_LETTERS_FOR_ASSESSMENT or stopword_share(text) < MIN_SPANISH_STOPWORD_SHARE:
        return TextQualityReport(TextQuality.NOT_ASSESSABLE, letters, accents_per_100)
    if accents_per_100 < MIN_ACCENTS_PER_100_LETTERS:
        return TextQualityReport(TextQuality.SUSPECT, letters, accents_per_100)
    return TextQualityReport(TextQuality.GOOD, letters, accents_per_100)
