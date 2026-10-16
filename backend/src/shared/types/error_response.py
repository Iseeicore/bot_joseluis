from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from src.shared.enums.error_code import ErrorCode


class ErrorDetail(BaseModel):
    path: str
    message: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    success: Literal[False] = False
    status_code: int
    error_code: ErrorCode
    message: str
    timestamp: str
    path: str
    details: list[ErrorDetail] | None = None
