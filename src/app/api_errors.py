from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.contracts.error import ErrorResponse
from app.error_response import error_response
from app.upstream_errors import UpstreamServiceError

ExceptionHandler = Callable[[Request, Exception], Response | Awaitable[Response]]

ERROR_RESPONSE_400: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "Invalid input for business rule evaluation.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "Unsupported period type: BAD",
                    "correlation_id": "corr-123",
                }
            }
        }
    },
}
ERROR_RESPONSE_403: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "Authorization denied by enterprise policy.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "AUTHORIZATION_DENIED",
                    "message": "authorization_policy_denied",
                    "correlation_id": "corr-123",
                    "details": {"reason": "missing_headers:x-actor-id"},
                }
            }
        }
    },
}
ERROR_RESPONSE_404: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "Endpoint or resource not found.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Not Found",
                    "correlation_id": "corr-123",
                }
            }
        }
    },
}
ERROR_RESPONSE_422: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "Request payload validation failed.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request validation failed",
                    "correlation_id": "corr-123",
                    "details": [
                        {"loc": ["body", "periods", 0, "to_date"], "msg": "Field required"}
                    ],
                }
            }
        }
    },
}
ERROR_RESPONSE_DEFAULT: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "Unhandled service error.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "REQUEST_REJECTED",
                    "message": "Unexpected error",
                    "correlation_id": "corr-123",
                }
            }
        }
    },
}
STANDARD_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: ERROR_RESPONSE_400,
    424: {
        "model": ErrorResponse,
        "description": "Dependency rejected the request or did not provide required data.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "FAILED_DEPENDENCY",
                        "message": "lotus-performance /integration/returns/series rejected request (404): missing benchmark assignment",
                        "correlation_id": "corr-123",
                        "details": {
                            "service": "lotus-performance",
                            "operation": "/integration/returns/series",
                            "upstream_status_code": 404,
                            "retryable": False,
                        },
                    }
                }
            }
        },
    },
    403: ERROR_RESPONSE_403,
    404: ERROR_RESPONSE_404,
    422: ERROR_RESPONSE_422,
    502: {
        "model": ErrorResponse,
        "description": "Dependency returned an invalid or failing upstream response.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "UPSTREAM_FAILURE",
                        "message": "lotus-performance /integration/returns/series failed (503): upstream failed",
                        "correlation_id": "corr-123",
                        "details": {
                            "service": "lotus-performance",
                            "operation": "/integration/returns/series",
                            "upstream_status_code": 503,
                            "retryable": True,
                        },
                    }
                }
            }
        },
    },
    503: {
        "model": ErrorResponse,
        "description": "Dependency is unavailable or service is draining.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "UPSTREAM_UNAVAILABLE",
                        "message": "lotus-core /integration/reference/risk-free-series unavailable: network down",
                        "correlation_id": "corr-123",
                        "details": {
                            "service": "lotus-core",
                            "operation": "/integration/reference/risk-free-series",
                            "retryable": True,
                        },
                    }
                }
            }
        },
    },
    504: {
        "model": ErrorResponse,
        "description": "Dependency request timed out.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "UPSTREAM_TIMEOUT",
                        "message": "lotus-core /integration/reference/risk-free-series timed out: request timed out",
                        "correlation_id": "corr-123",
                        "details": {
                            "service": "lotus-core",
                            "operation": "/integration/reference/risk-free-series",
                            "retryable": True,
                        },
                    }
                }
            }
        },
    },
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
