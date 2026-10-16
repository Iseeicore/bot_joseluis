import re

LETTER_PATTERN = re.compile(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü]")
ACCENT_PATTERN = re.compile(r"[ÁÉÍÓÚÑÜáéíóúñü]")
WORD_PATTERN = re.compile(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü]+")
