from http import HTTPStatus

from src.shared.constants.texts.documents import DOCUMENT_WITHOUT_TEXT_TEXT
from src.shared.enums.error_code import ErrorCode
from src.shared.errors.app_error import AppError


class DocumentWithoutTextError(AppError):
    def __init__(self, filename: str) -> None:
        super().__init__(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            error_code=ErrorCode.DOCUMENT_WITHOUT_TEXT,
            message=DOCUMENT_WITHOUT_TEXT_TEXT,
        )
        self.filename = filename
