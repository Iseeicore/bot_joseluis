from http import HTTPStatus

from src.shared.constants.texts.documents import CORRUPT_DOCUMENT_TEXT
from src.shared.enums.error_code import ErrorCode
from src.shared.errors.app_error import AppError


class CorruptDocumentError(AppError):
    def __init__(self, filename: str) -> None:
        super().__init__(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            error_code=ErrorCode.CORRUPT_DOCUMENT,
            message=CORRUPT_DOCUMENT_TEXT,
        )
        self.filename = filename
