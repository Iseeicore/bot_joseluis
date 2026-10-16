from http import HTTPStatus

from src.shared.constants.texts.llm import EMPTY_MODEL_ANSWER_TEXT
from src.shared.enums.error_code import ErrorCode
from src.shared.errors.app_error import AppError


class EmptyModelAnswerError(AppError):
    def __init__(self, model: str, position: int) -> None:
        super().__init__(
            status_code=HTTPStatus.BAD_GATEWAY,
            error_code=ErrorCode.EMPTY_MODEL_ANSWER,
            message=EMPTY_MODEL_ANSWER_TEXT,
        )
        self.model = model
        self.position = position
