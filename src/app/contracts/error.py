from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    message: str
    correlation_id: str | None = Field(default=None, alias="correlationId")
    details: Any | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    error: ErrorBody
