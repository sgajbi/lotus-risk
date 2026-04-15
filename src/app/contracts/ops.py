from __future__ import annotations

from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    service: str = Field(
        description="Dependency service identifier.",
        json_schema_extra={"example": "lotus-core"},
    )
    base_url: str = Field(
        description="Canonical base URL configured for the dependency.",
        json_schema_extra={"example": "http://core-control.dev.lotus"},
    )
    status: str = Field(
        description="Dependency runtime state.",
        json_schema_extra={"example": "ok"},
    )
    detail: str | None = Field(
        default=None,
        description="Additional runtime detail for operators.",
        json_schema_extra={"example": "configured"},
    )
    category: str | None = Field(
        default=None,
        description="Optional structured dependency issue category such as transport, timeout, or data_gap.",
        json_schema_extra={"example": "data_gap"},
    )
    issue_code: str | None = Field(
        default=None,
        description="Optional machine-readable issue code for degraded or unavailable dependency state.",
        json_schema_extra={"example": "RISK_FREE_SERIES_EMPTY"},
    )


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
    dependencies: list[DependencyStatus] = Field(
        description="Runtime dependency diagnostics used for readiness and operations.",
        json_schema_extra={
            "example": [
                {
                    "service": "lotus-core",
                    "base_url": "http://core-control.dev.lotus",
                    "status": "ok",
                    "detail": "configured",
                }
            ]
        },
    )
