from src.shared.constants.limits.note_facts import MIN_NUMERIC_FACT_LENGTH
from src.shared.constants.regex.note_facts import (
    CAPITALS_WORD_PATTERN,
    EDGE_PUNCTUATION,
    NON_ALPHANUMERIC_PATTERN,
    NUMERIC_TOKEN_PATTERN,
    WORD_PATTERN,
)
from src.shared.utils.strip_accents import strip_accents


def squash(text: str) -> str:
    return NON_ALPHANUMERIC_PATTERN.sub("", strip_accents(text).lower())


def numeric_facts(note: str) -> list[str]:
    tokens = (token.strip(EDGE_PUNCTUATION) for token in NUMERIC_TOKEN_PATTERN.findall(note))
    return [token for token in tokens if len(squash(token)) >= MIN_NUMERIC_FACT_LENGTH]


def find_unverified_facts(note: str, chunk: str) -> tuple[str, ...]:
    squashed_chunk = squash(chunk)
    chunk_words = set(WORD_PATTERN.findall(strip_accents(chunk).lower()))
    candidates = [
        *((fact, squash(fact) in squashed_chunk) for fact in numeric_facts(note)),
        *((word, strip_accents(word).lower() in chunk_words) for word in CAPITALS_WORD_PATTERN.findall(note)),
    ]
    ordered = sorted(candidates, key=lambda item: note.find(item[0]))
    missing = [fact for fact, found in ordered if not found]
    return tuple(dict.fromkeys(missing))
