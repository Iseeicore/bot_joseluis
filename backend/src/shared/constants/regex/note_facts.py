import re

NUMERIC_TOKEN_PATTERN = re.compile(r"\S*\d\S*")
CAPITALS_WORD_PATTERN = re.compile(r"\b[A-ZÁÉÍÓÚÑ]{4,}\b")
NON_ALPHANUMERIC_PATTERN = re.compile(r"[^0-9a-z]")
WORD_PATTERN = re.compile(r"[0-9a-z]+")
EDGE_PUNCTUATION = ".,;:()[]\"'¿?¡!-"

FINGERPRINT_PATTERN = re.compile(r"[0-9a-f]{64}")
ALPHANUMERIC_CHAR_PATTERN = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")
