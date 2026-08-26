from __future__ import annotations

from typing import Any, cast

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.contracts.error import ErrorBody, ErrorResponse


def _problem_type(code: str) -> str:
    return f"urn:lotus-risk:error:{code.lower().replace('_', '-')}"


def _problem_title(code: str) -> str:
    return code.replace("_", " ").title()


def _resolve_correlation_id(request: Request) -> str | None:
    return (
        getattr(request.state, "correlation_id", None)
        or request.headers.get("X-Correlation-Id")
        or None
    )


def build_error_payload(
    request: Request,
    *,
    status_code: int | None = None,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    payload = ErrorResponse(
        error=ErrorBody(
            type=_problem_type(code) if status_code is not None else None,
            title=_problem_title(code) if status_code is not None else None,
            status=status_code,
            detail=message if status_code is not None else None,
            instance=request.url.path if status_code is not None else None,
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
            status_code=status_code,
            code=code,
            message=message,
            details=details,
        ),
    )
