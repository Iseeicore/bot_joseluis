from http import HTTPStatus

from src.shared.constants.texts.documents import ENCRYPTED_DOCUMENT_TEXT
from src.shared.enums.error_code import ErrorCode
from src.shared.errors.app_error import AppError


class EncryptedDocumentError(AppError):
    def __init__(self, filename: str) -> None:
        super().__init__(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            error_code=ErrorCode.ENCRYPTED_DOCUMENT,
            message=ENCRYPTED_DOCUMENT_TEXT,
        )
        self.filename = filename
