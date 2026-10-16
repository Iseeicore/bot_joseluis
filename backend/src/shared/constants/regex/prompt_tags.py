import re

PROMPT_TAG_PATTERN = re.compile(r"<\s*/?\s*(documento|solicitud|fragmento|notas)\s*>", re.IGNORECASE)
