from __future__ import annotations

from typing import Any
from typing import cast

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.contracts.error import ErrorBody, ErrorResponse


def _resolve_correlation_id(request: Request) -> str | None:
    return (
        getattr(request.state, "correlation_id", None)
        or request.headers.get("X-Correlation-Id")
        or None
    )


def build_error_payload(
    request: Request,
    *,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    payload = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            correlation_id=_resolve_correlation_id(request),
            details=details,
        )
    )
    return cast(
        dict[str, Any],
        jsonable_encoder(payload.model_dump(exclude_none=True)),
    )


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=build_error_payload(
            request,
            code=code,
            message=message,
            details=details,
        ),
    )
