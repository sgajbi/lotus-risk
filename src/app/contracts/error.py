from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str = Field(
        description="Stable machine-readable error code.",
        json_schema_extra={"example": "INVALID_REQUEST"},
    )
    message: str = Field(
        description="Human-readable error message suitable for logs and diagnostics.",
        json_schema_extra={"example": "Request validation failed"},
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation identifier propagated from request context.",
        json_schema_extra={"example": "corr-123"},
    )
    details: Any | None = Field(
        default=None,
        description="Optional structured error details.",
        json_schema_extra={"example": [{"loc": ["body", "periods"], "msg": "Field required"}]},
    )


class ErrorResponse(BaseModel):
    error: ErrorBody = Field(
        description="Wrapped error payload using Lotus standard envelope.",
        json_schema_extra={
            "example": {
                "code": "INVALID_REQUEST",
                "message": "Request validation failed",
                "correlation_id": "corr-123",
            }
        },
    )
