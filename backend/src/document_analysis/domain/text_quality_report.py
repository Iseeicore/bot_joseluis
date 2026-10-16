from dataclasses import dataclass

from src.shared.enums.text_quality import TextQuality


@dataclass(frozen=True)
class TextQualityReport:
    verdict: TextQuality
    letters: int
    accents_per_100_letters: float
