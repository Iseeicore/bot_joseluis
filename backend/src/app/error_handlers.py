import logging
from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.shared.constants.formats import TIMESTAMP_FORMAT
from src.shared.constants.texts.errors import INTERNAL_ERROR_TEXT, NOT_FOUND_TEXT, VALIDATION_ERROR_TEXT
from src.shared.enums.error_code import ErrorCode
from src.shared.errors.app_error import AppError
from src.shared.types.error_response import ErrorDetail, ErrorResponse

NOT_FOUND_STATUS = 404
VALIDATION_STATUS = 400
INTERNAL_STATUS = 500

logger = logging.getLogger(__name__)
Clock = Callable[[], datetime]


def build_response(
    request: Request,
    now: Clock,
    status_code: int,
    error_code: ErrorCode,
    message: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        status_code=status_code,
        error_code=error_code,
        message=message,
        timestamp=now().strftime(TIMESTAMP_FORMAT),
        path=request.url.path,
        details=details,
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(by_alias=True, exclude_none=True, mode="json"))


def to_details(error: RequestValidationError) -> list[ErrorDetail]:
    return [ErrorDetail(path=".".join(str(part) for part in item["loc"]), message=item["msg"]) for item in error.errors()]


def register_error_handlers(app: FastAPI, now: Clock) -> None:
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        return build_response(request, now, error.status_code, error.error_code, error.message, error.details)

    async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        return build_response(request, now, VALIDATION_STATUS, ErrorCode.VALIDATION_ERROR, VALIDATION_ERROR_TEXT, to_details(error))

    async def handle_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        if error.status_code == NOT_FOUND_STATUS:
            return build_response(request, now, NOT_FOUND_STATUS, ErrorCode.NOT_FOUND, NOT_FOUND_TEXT)
        return build_response(request, now, error.status_code, ErrorCode.HTTP_ERROR, str(error.detail))

    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s", request.url.path, exc_info=error)
        return build_response(request, now, INTERNAL_STATUS, ErrorCode.INTERNAL_ERROR, INTERNAL_ERROR_TEXT)

    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
