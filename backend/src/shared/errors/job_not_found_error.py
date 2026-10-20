from http import HTTPStatus

from src.shared.constants.texts.jobs import JOB_NOT_FOUND_TEXT
from src.shared.enums.error_code import ErrorCode
from src.shared.errors.app_error import AppError


class JobNotFoundError(AppError):
    def __init__(self, job_id: str) -> None:
        super().__init__(
            status_code=HTTPStatus.NOT_FOUND,
            error_code=ErrorCode.JOB_NOT_FOUND,
            message=JOB_NOT_FOUND_TEXT,
        )
        self.job_id = job_id
