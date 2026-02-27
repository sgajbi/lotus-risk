from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi import Request
from fastapi.responses import JSONResponse

from app.contracts.error import ErrorBody, ErrorResponse


def _resolve_correlation_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            correlationId=_resolve_correlation_id(request),
            details=details,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload.model_dump(by_alias=True, exclude_none=True)),
    )
