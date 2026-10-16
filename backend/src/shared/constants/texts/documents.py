DOCUMENT_WITHOUT_TEXT_TEXT = "El documento no contiene texto extraíble (posible escaneo)."
CORRUPT_DOCUMENT_TEXT = "El archivo está dañado o no es un documento válido."
ENCRYPTED_DOCUMENT_TEXT = "El documento está protegido con contraseña."


def invalid_fingerprint_text(fingerprint: str) -> str:
    return f"Huella no válida: {fingerprint!r}"
