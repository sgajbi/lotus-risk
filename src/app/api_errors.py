from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api_error_examples import STANDARD_ERROR_RESPONSES
from app.error_response import error_response
from app.upstream_errors import UpstreamServiceError

ExceptionHandler = Callable[[Request, Exception], Response | Awaitable[Response]]


def _default_error_code(status_code: int) -> str:
    if status_code == status.HTTP_404_NOT_FOUND:
        return "RESOURCE_NOT_FOUND"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "AUTHORIZATION_DENIED"
    if status_code == status.HTTP_413_CONTENT_TOO_LARGE:
        return "PAYLOAD_TOO_LARGE"
    if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
        return "INVALID_REQUEST"
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "INVALID_INPUT"
    return "REQUEST_REJECTED"


async def handle_validation_error(request: Request, exc: RequestValidationError) -> Response:
    return error_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="INVALID_REQUEST",
        message="Request validation failed",
        details=exc.errors(),
    )


async def handle_starlette_http_exception(
    request: Request, exc: StarletteHTTPException
) -> Response:
    return error_response(
        request,
        status_code=exc.status_code,
        code=_default_error_code(exc.status_code),
        message=str(exc.detail),
    )


async def handle_http_exception(request: Request, exc: HTTPException) -> Response:
    return error_response(
        request,
        status_code=exc.status_code,
        code=_default_error_code(exc.status_code),
        message=str(exc.detail),
    )


async def handle_value_error(request: Request, exc: ValueError) -> Response:
    return error_response(
        request,
        status_code=status.HTTP_400_BAD_REQUEST,
        code="INVALID_INPUT",
        message=str(exc),
    )


async def handle_upstream_service_error(request: Request, exc: UpstreamServiceError) -> Response:
    details = dict(exc.details)
    details["retryable"] = exc.retryable
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=details,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, handle_validation_error)
    )
    app.add_exception_handler(
        StarletteHTTPException,
        cast(ExceptionHandler, handle_starlette_http_exception),
    )
    app.add_exception_handler(HTTPException, cast(ExceptionHandler, handle_http_exception))
    app.add_exception_handler(ValueError, cast(ExceptionHandler, handle_value_error))
    app.add_exception_handler(
        UpstreamServiceError,
        cast(ExceptionHandler, handle_upstream_service_error),
    )


__all__ = ["STANDARD_ERROR_RESPONSES", "register_exception_handlers"]
