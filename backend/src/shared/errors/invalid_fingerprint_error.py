from src.shared.constants.texts.documents import invalid_fingerprint_text


class InvalidFingerprintError(ValueError):
    def __init__(self, fingerprint: str) -> None:
        super().__init__(invalid_fingerprint_text(fingerprint))
        self.fingerprint = fingerprint
