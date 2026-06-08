from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.contracts.error import ErrorResponse
from app.error_response import error_response
from app.upstream_errors import UpstreamServiceError

ExceptionHandler = Callable[[Request, Exception], Response | Awaitable[Response]]


def _problem_type(code: str) -> str:
    return f"urn:lotus-risk:error:{code.lower().replace('_', '-')}"


def _problem_title(code: str) -> str:
    return code.replace("_", " ").title()


def _error_example(
    *,
    status_code: int,
    code: str,
    message: str,
    instance: str,
    details: Any | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "type": _problem_type(code),
        "title": _problem_title(code),
        "status": status_code,
        "detail": message,
        "instance": instance,
        "code": code,
        "message": message,
        "correlation_id": "corr-123",
    }
    if details is not None:
        error["details"] = details
    return {"error": error}


def _error_response_metadata(
    *,
    description: str,
    status_code: int,
    code: str,
    message: str,
    instance: str,
    details: Any | None = None,
) -> dict[str, Any]:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "example": _error_example(
                    status_code=status_code,
                    code=code,
                    message=message,
                    instance=instance,
                    details=details,
                )
            }
        },
    }


ERROR_RESPONSE_400 = _error_response_metadata(
    description="Invalid input for business rule evaluation.",
    status_code=400,
    code="INVALID_INPUT",
    message="Unsupported period type: BAD",
    instance="/analytics/risk/calculate",
)
ERROR_RESPONSE_403 = _error_response_metadata(
    description="Authorization denied by enterprise policy.",
    status_code=403,
    code="AUTHORIZATION_DENIED",
    message="authorization_policy_denied",
    instance="/analytics/risk/calculate",
    details={"reason": "missing_headers:x-actor-id"},
)
ERROR_RESPONSE_404 = _error_response_metadata(
    description="Endpoint or resource not found.",
    status_code=404,
    code="RESOURCE_NOT_FOUND",
    message="Not Found",
    instance="/unknown",
)
ERROR_RESPONSE_422 = _error_response_metadata(
    description="Request payload validation failed.",
    status_code=422,
    code="INVALID_REQUEST",
    message="Request validation failed",
    instance="/analytics/risk/calculate",
    details=[{"loc": ["body", "periods", 0, "to_date"], "msg": "Field required"}],
)
ERROR_RESPONSE_DEFAULT = _error_response_metadata(
    description="Unhandled service error.",
    status_code=500,
    code="REQUEST_REJECTED",
    message="Unexpected error",
    instance="/analytics/risk/calculate",
)
STANDARD_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: ERROR_RESPONSE_400,
    424: _error_response_metadata(
        description="Dependency rejected the request or did not provide required data.",
        status_code=424,
        code="FAILED_DEPENDENCY",
        message="lotus-performance /integration/returns/series rejected request (404)",
        instance="/analytics/risk/calculate",
        details={
            "service": "lotus-performance",
            "operation": "/integration/returns/series",
            "upstream_status_code": 404,
            "retryable": False,
        },
    ),
    403: ERROR_RESPONSE_403,
    404: ERROR_RESPONSE_404,
    422: ERROR_RESPONSE_422,
    502: _error_response_metadata(
        description="Dependency returned an invalid or failing upstream response.",
        status_code=502,
        code="UPSTREAM_FAILURE",
        message="lotus-performance /integration/returns/series failed (503)",
        instance="/analytics/risk/calculate",
        details={
            "service": "lotus-performance",
            "operation": "/integration/returns/series",
            "upstream_status_code": 503,
            "retryable": True,
        },
    ),
    503: _error_response_metadata(
        description="Dependency is unavailable or service is draining.",
        status_code=503,
        code="UPSTREAM_UNAVAILABLE",
        message="lotus-core /integration/reference/risk-free-series unavailable",
        instance="/analytics/risk/rolling-metrics",
        details={
            "service": "lotus-core",
            "operation": "/integration/reference/risk-free-series",
            "retryable": True,
        },
    ),
    504: _error_response_metadata(
        description="Dependency request timed out.",
        status_code=504,
        code="UPSTREAM_TIMEOUT",
        message="lotus-core /integration/reference/risk-free-series timed out",
        instance="/analytics/risk/rolling-metrics",
        details={
            "service": "lotus-core",
            "operation": "/integration/reference/risk-free-series",
            "retryable": True,
        },
    ),
    "default": ERROR_RESPONSE_DEFAULT,
}


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
