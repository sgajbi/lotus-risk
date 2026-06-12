from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    type: str | None = Field(
        default=None,
        description="RFC 7807 problem type URI for the error category.",
        json_schema_extra={"example": "urn:lotus-risk:error:invalid-request"},
    )
    title: str | None = Field(
        default=None,
        description="Short RFC 7807 problem title.",
        json_schema_extra={"example": "Invalid request"},
    )
    status: int | None = Field(
        default=None,
        description="HTTP status code for RFC 7807 problem-details compatibility.",
        json_schema_extra={"example": 422},
    )
    detail: str | None = Field(
        default=None,
        description="RFC 7807 problem detail. Mirrors the Lotus error message.",
        json_schema_extra={"example": "Request validation failed"},
    )
    instance: str | None = Field(
        default=None,
        description="Request path associated with this problem instance.",
        json_schema_extra={"example": "/risk/calculate"},
    )
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
                "type": "urn:lotus-risk:error:invalid-request",
                "title": "Invalid request",
                "status": 422,
                "detail": "Request validation failed",
                "instance": "/risk/calculate",
                "code": "INVALID_REQUEST",
                "message": "Request validation failed",
                "correlation_id": "corr-123",
            }
        },
    )
