REMOVED_TAG_TEXT = "[etiqueta eliminada]"


def user_message_text(request: str, document: str) -> str:
    return f"<solicitud>\n{request}\n</solicitud>\n\n<documento>\n{document}\n</documento>"


def page_marker_text(number: int, source: str) -> str:
    return f"[Página {number} | {source}]"


def notes_user_message_text(fragment: str) -> str:
    return f"<fragmento>\n{fragment}\n</fragmento>"


NO_CONTENT_NOTE_TEXT = "- Sin contenido relevante"
UNREADABLE_NOTE_TEXT = "- No se pudo generar la nota de este fragmento"


def pages_label(first_page: int, last_page: int) -> str:
    return f"[págs. {first_page}-{last_page}]"


def summary_user_message_text(request: str, notes: str) -> str:
    return f"<solicitud>\n{request}\n</solicitud>\n\n<notas>\n{notes}\n</notas>"


def columns_line_text(headers: list[str]) -> str:
    return f"[Columnas: {' | '.join(headers)}]"


def marked_row_text(label: str, columns: list[str]) -> str:
    return f"{label} -> {'; '.join(columns)}"
