from __future__ import annotations

from pydantic import BaseModel, Field


class OpsChecks(BaseModel):
    live: bool = Field(
        description="Liveness check status.",
        json_schema_extra={"example": True},
    )
    ready: bool = Field(
        description="Readiness check status.",
        json_schema_extra={"example": True},
    )
    draining: bool = Field(
        description="Whether the service is currently in draining mode.",
        json_schema_extra={"example": False},
    )


class OpsResponse(BaseModel):
    service: str = Field(
        description="Service identifier.",
        json_schema_extra={"example": "lotus-risk"},
    )
    version: str = Field(
        description="Service version.",
        json_schema_extra={"example": "0.1.0"},
    )
    status: str = Field(
        description="Overall operational status.",
        json_schema_extra={"example": "ok"},
    )
    checks: OpsChecks = Field(
        description="Detailed health checks.",
        json_schema_extra={"example": {"live": True, "ready": True, "draining": False}},
    )
    input_modes: list[str] = Field(
        description="Execution modes exposed by this service.",
        json_schema_extra={"example": ["stateless", "stateful", "simulation"]},
    )
