from http import HTTPStatus

from src.shared.constants.texts.llm import LLM_UNAVAILABLE_TEXT
from src.shared.enums.error_code import ErrorCode
from src.shared.errors.app_error import AppError


class LlmUnavailableError(AppError):
    def __init__(self, model: str) -> None:
        super().__init__(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            error_code=ErrorCode.LLM_UNAVAILABLE,
            message=LLM_UNAVAILABLE_TEXT,
        )
        self.model = model
