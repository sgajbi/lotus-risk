from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RollingBenchmarkContext(BaseModel):
    requested: bool = Field(
        description="Whether any benchmark-dependent rolling metrics were requested for this period.",
        json_schema_extra={"example": True},
    )
    available: bool = Field(
        description="Whether benchmark return observations were available in this period.",
        json_schema_extra={"example": True},
    )
    aligned: bool = Field(
        description="Whether benchmark return observations aligned with portfolio observations for requested rolling metrics.",
        json_schema_extra={"example": True},
    )
    reason: Literal[
        "NOT_REQUESTED", "BENCHMARK_UNAVAILABLE", "NO_ALIGNED_OBSERVATIONS", "APPLIED"
    ] = Field(
        description="Deterministic benchmark application outcome for the period.",
        json_schema_extra={"example": "APPLIED"},
    )


class RollingRiskFreeContext(BaseModel):
    requested: bool = Field(
        description="Whether rolling Sharpe was requested for this period.",
        json_schema_extra={"example": True},
    )
    available: bool = Field(
        description="Whether risk-free observations were available in this period.",
        json_schema_extra={"example": True},
    )
    aligned: bool = Field(
        description="Whether risk-free observations aligned with portfolio observations for rolling Sharpe.",
        json_schema_extra={"example": True},
    )
    reason: Literal[
        "NOT_REQUESTED", "RISK_FREE_UNAVAILABLE", "NO_ALIGNED_OBSERVATIONS", "APPLIED"
    ] = Field(
        description="Deterministic risk-free application outcome for the period.",
        json_schema_extra={"example": "APPLIED"},
    )


__all__ = [
    "RollingBenchmarkContext",
    "RollingRiskFreeContext",
]
