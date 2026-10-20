from http import HTTPStatus

from src.shared.constants.texts.jobs import EMPTY_UPLOAD_TEXT
from src.shared.enums.error_code import ErrorCode
from src.shared.errors.app_error import AppError


class EmptyUploadError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=HTTPStatus.BAD_REQUEST,
            error_code=ErrorCode.EMPTY_FILE,
            message=EMPTY_UPLOAD_TEXT,
        )
