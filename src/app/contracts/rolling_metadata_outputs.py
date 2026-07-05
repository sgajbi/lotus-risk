from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.audit import AuditMetadataFields
from app.contracts.risk import RiskCalculationSupportability
from app.contracts.rolling_response_field_examples import (
    ROLLING_BENCHMARK_CONTEXT_EXAMPLE,
    ROLLING_CALCULATION_SUPPORTABILITY_EXAMPLE,
    ROLLING_REQUESTED_METRICS_EXAMPLE,
    ROLLING_RISK_FREE_CONTEXT_EXAMPLE,
)


class RollingRequestDependencyContext(BaseModel):
    requested: bool = Field(
        description="Whether this dependency family is required by any requested rolling metric.",
        json_schema_extra={"example": True},
    )
    requested_metrics: list[str] = Field(
        default_factory=list,
        description="Requested rolling metrics that depend on this family.",
        json_schema_extra={"example": ["ROLLING_BETA", "ROLLING_TRACKING_ERROR"]},
    )


class RollingMetadata(AuditMetadataFields):
    product_name: Literal["RollingRiskMetricsReport"] = Field(
        default="RollingRiskMetricsReport",
        description="Source-owned domain data product emitted by this response.",
        json_schema_extra={"example": "RollingRiskMetricsReport"},
    )
    product_version: Literal["v1"] = Field(
        default="v1",
        description="Source-owned domain data product version.",
        json_schema_extra={"example": "v1"},
    )
    contract_version: str = Field(
        default="v1",
        description="Rolling metrics contract version.",
        json_schema_extra={"example": "v1"},
    )
    methodology_version: str = Field(
        default="rolling_metrics.v1",
        description="Methodology version used for rolling metric formulas.",
        json_schema_extra={"example": "rolling_metrics.v1"},
    )
    annualization_basis: int = Field(
        description="Annualization basis used for annualized rolling metrics.",
        json_schema_extra={"example": 252},
    )
    requested_metrics: list[str] = Field(
        default_factory=list,
        description="Requested rolling metrics in canonical execution order.",
        json_schema_extra={"example": ROLLING_REQUESTED_METRICS_EXAMPLE},
    )
    window_lengths_requested: list[int] = Field(
        default_factory=list,
        description="Rolling window lengths requested for this response.",
        json_schema_extra={"example": [21, 63, 126]},
    )
    window_count_requested: int = Field(
        default=0,
        description="Number of rolling window lengths requested for this response.",
        json_schema_extra={"example": 3},
    )
    alignment_policy: Literal["INNER_JOIN"] = Field(
        description="Series alignment policy used for multi-series rolling metrics.",
        json_schema_extra={"example": "INNER_JOIN"},
    )
    min_observations_policy: Literal["STRICT", "ALLOW_PARTIAL"] = Field(
        description="Minimum-observations policy used across the requested rolling windows.",
        json_schema_extra={"example": "STRICT"},
    )
    include_time_series: bool = Field(
        description="Whether rolling metric time-series points were requested for emitted windows.",
        json_schema_extra={"example": False},
    )
    benchmark_context: RollingRequestDependencyContext = Field(
        description="Top-level benchmark dependency context derived from the requested rolling metrics.",
        json_schema_extra={"example": ROLLING_BENCHMARK_CONTEXT_EXAMPLE},
    )
    risk_free_context: RollingRequestDependencyContext = Field(
        description="Top-level risk-free dependency context derived from the requested rolling metrics.",
        json_schema_extra={"example": ROLLING_RISK_FREE_CONTEXT_EXAMPLE},
    )
    calculation_supportability: RiskCalculationSupportability = Field(
        default_factory=lambda: RiskCalculationSupportability(
            state="ready",
            reason="calculation_complete",
            freshness_bucket="unknown",
        ),
        description="Source-backed supportability posture for UI and operator consumption.",
        json_schema_extra={"example": ROLLING_CALCULATION_SUPPORTABILITY_EXAMPLE},
    )


__all__ = [
    "RollingMetadata",
    "RollingRequestDependencyContext",
]
