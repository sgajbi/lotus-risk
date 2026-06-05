from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.risk_inputs import (
    RiskFreshnessBucket,
    RiskSupportabilityReason,
    RiskSupportabilityState,
)
from app.observability_contracts import RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS


class RiskFreeContext(BaseModel):
    requested: bool = Field(
        default=False,
        description="Whether any requested metrics depend on risk-free configuration.",
        json_schema_extra={"example": True},
    )
    applied: bool = Field(
        default=False,
        description="Whether risk-free configuration was applied to at least one requested metric.",
        json_schema_extra={"example": True},
    )
    reason: Literal["NOT_REQUESTED", "ZERO_RATE", "ANNUAL_RATE_APPLIED"] = Field(
        default="NOT_REQUESTED",
        description="Deterministic explanation of how risk-free configuration affected this response.",
        json_schema_extra={"example": "ANNUAL_RATE_APPLIED"},
    )
    periodic_rate: float = Field(
        default=0.0,
        description="Applied periodic risk-free rate as a decimal return after annualization.",
        json_schema_extra={"example": 0.00003949},
    )


class BenchmarkRequestContext(BaseModel):
    requested: bool = Field(
        default=False,
        description="Whether any requested metrics depend on benchmark return alignment.",
        json_schema_extra={"example": True},
    )
    requested_metrics: list[str] = Field(
        default_factory=list,
        description="Benchmark-dependent metrics requested anywhere in this response.",
        json_schema_extra={"example": ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"]},
    )


class RiskCalculationSupportability(BaseModel):
    state: RiskSupportabilityState = Field(
        description="Bounded supportability state for the risk calculation payload.",
        json_schema_extra={"example": "ready"},
    )
    reason: RiskSupportabilityReason = Field(
        description="Bounded supportability reason that is safe for UI and operator metrics.",
        json_schema_extra={"example": "calculation_complete"},
    )
    freshness_bucket: RiskFreshnessBucket = Field(
        description="Bounded source freshness bucket based on the latest return observation.",
        json_schema_extra={"example": "current"},
    )
    metric_labels: tuple[str, ...] = Field(
        default=RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS,
        description=(
            "Bounded Prometheus label keys emitted by "
            "lotus_risk_calculation_supportability_total. Identifiers, trace or "
            "correlation values, and request or response payload fields must not be "
            "metric labels."
        ),
        json_schema_extra={
            "example": [
                "operation",
                "supportability_state",
                "reason",
                "freshness_bucket",
            ]
        },
    )
    degraded_metric_count: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of requested metric or period results carrying deterministic error details."
        ),
        json_schema_extra={"example": 0},
    )
    empty_period_count: int = Field(
        default=0,
        ge=0,
        description="Number of response periods with no portfolio observations.",
        json_schema_extra={"example": 0},
    )
    evaluated_period_count: int = Field(
        default=0,
        ge=0,
        description="Number of periods evaluated in this response.",
        json_schema_extra={"example": 1},
    )


__all__ = [
    "BenchmarkRequestContext",
    "RiskCalculationSupportability",
    "RiskFreeContext",
]
