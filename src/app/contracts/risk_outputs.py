from __future__ import annotations

import datetime as dt
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.audit import AuditMetadataFields
from app.contracts.risk_examples import RISK_RESPONSE_EXAMPLE
from app.contracts.risk_inputs import (
    RiskFreshnessBucket,
    RiskRequestScope,
    RiskSupportabilityReason,
    RiskSupportabilityState,
)
from app.observability_contracts import RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS


class RiskValue(BaseModel):
    value: float | None = Field(  # monetary-float-allow: risk metric value, not money.
        default=None,
        description="Computed metric value.",
        json_schema_extra={"example": 0.1234},
    )
    details: dict[str, str | float | int | bool | None] | None = Field(
        default=None,
        description="Optional metric-specific details or deterministic error payload.",
        json_schema_extra={
            "example": {
                "observation_count": 64,
                "annualization_factor": 252,
                "mean_return": 0.0010093159,
                "periodic_risk_free_rate": 0.0,
                "excess_return": 0.0010093159,
                "annualized_excess_return": 0.254347604,
                "volatility": 0.0078985986,
            }
        },
    )


class RiskPeriodResult(BaseModel):
    start_date: dt.date = Field(
        description="Resolved period start date after semantic normalization.",
        json_schema_extra={"example": "2025-01-01"},
    )
    end_date: dt.date = Field(
        description="Resolved period end date after semantic normalization.",
        json_schema_extra={"example": "2025-03-31"},
    )
    portfolio_observation_count: int = Field(
        default=0,
        description="Number of portfolio return observations used for this period result.",
        json_schema_extra={"example": 64},
    )
    benchmark_observation_count: int = Field(
        default=0,
        description="Number of benchmark return observations available for this period result.",
        json_schema_extra={"example": 64},
    )
    aligned_benchmark_observation_count: int = Field(
        default=0,
        description="Number of aligned portfolio/benchmark observations used for benchmark-dependent metrics.",
        json_schema_extra={"example": 61},
    )
    benchmark_context: dict[str, str | bool | int | list[str]] | None = Field(
        default=None,
        description="Execution context for benchmark-dependent metrics in this period.",
        json_schema_extra={
            "example": {
                "requested": True,
                "available": True,
                "aligned": True,
                "reason": "APPLIED",
                "requested_metric_count": 3,
                "requested_metrics": ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"],
            }
        },
    )
    metrics: dict[str, RiskValue] = Field(
        description="Metric values keyed by metric name.",
        json_schema_extra={"example": {"VOLATILITY": {"value": 9.75}, "SHARPE": {"value": 2.61}}},
    )


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


class RiskResponseMetadata(AuditMetadataFields):
    contract_version: str = Field(
        default="v1",
        description="Risk analytics contract version.",
        json_schema_extra={"example": "v1"},
    )
    methodology_version: str = Field(
        default="risk.v1",
        description="Methodology version used for the risk engine.",
        json_schema_extra={"example": "risk.v1"},
    )
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY"] = Field(
        default="DAILY",
        description="Applied return sampling frequency.",
        json_schema_extra={"example": "DAILY"},
    )
    annualization_factor: int = Field(
        default=252,
        description="Applied annualization factor after defaults or overrides.",
        json_schema_extra={"example": 252},
    )
    use_log_returns: bool = Field(
        default=False,
        description="Whether returns were transformed to log returns before metric evaluation.",
        json_schema_extra={"example": False},
    )
    risk_free_mode: Literal["ZERO", "ANNUAL_RATE"] = Field(
        default="ZERO",
        description="Applied risk-free mode for Sharpe calculations.",
        json_schema_extra={"example": "ZERO"},
    )
    risk_free_annual_rate: float | None = Field(
        default=None,
        description="Applied annual risk-free rate when risk_free_mode=ANNUAL_RATE.",
        json_schema_extra={"example": 0.01},
    )
    risk_free_context: RiskFreeContext = Field(
        default_factory=RiskFreeContext,
        description="Applied risk-free interpretation context for Sharpe calculations.",
        json_schema_extra={
            "example": {
                "requested": True,
                "applied": True,
                "reason": "ANNUAL_RATE_APPLIED",
                "periodic_rate": 0.00003949,
            }
        },
    )
    benchmark_context: BenchmarkRequestContext = Field(
        default_factory=BenchmarkRequestContext,
        description="Benchmark dependency request context for this response.",
        json_schema_extra={
            "example": {
                "requested": True,
                "requested_metrics": ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"],
            }
        },
    )
    calculation_supportability: RiskCalculationSupportability = Field(
        default_factory=lambda: RiskCalculationSupportability(
            state="ready",
            reason="calculation_complete",
            freshness_bucket="unknown",
        ),
        description="Source-backed supportability posture for UI and operator consumption.",
        json_schema_extra={
            "example": {
                "state": "ready",
                "reason": "calculation_complete",
                "freshness_bucket": "current",
                "degraded_metric_count": 0,
                "empty_period_count": 0,
                "evaluated_period_count": 1,
            }
        },
    )
    mar_annual_rate: float = Field(
        default=0.0,
        description="Applied annual minimum acceptable return for Sortino calculations.",
        json_schema_extra={"example": 0.0},
    )
    var_method: Literal["HISTORICAL", "GAUSSIAN", "CORNISH_FISHER"] = Field(
        default="HISTORICAL",
        description="Applied Value-at-Risk method.",
        json_schema_extra={"example": "HISTORICAL"},
    )
    var_confidence: float = Field(
        default=0.99,
        description="Applied Value-at-Risk confidence level.",
        json_schema_extra={"example": 0.95},
    )
    var_horizon_days: int = Field(
        default=1,
        description="Applied Value-at-Risk horizon in business days.",
        json_schema_extra={"example": 1},
    )


class RiskResponse(BaseModel):
    scope: RiskRequestScope = Field(
        description="Echoed normalized scope context used for calculation.",
        json_schema_extra={
            "example": {
                "as_of_date": "2025-03-31",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    results: dict[str, RiskPeriodResult] = Field(
        description="Risk results keyed by period name or period type.",
        json_schema_extra={
            "example": {
                "explicit_q1_2025": {
                    "start_date": "2025-01-01",
                    "end_date": "2025-03-31",
                    "portfolio_observation_count": 64,
                    "benchmark_observation_count": 64,
                    "aligned_benchmark_observation_count": 61,
                    "benchmark_context": {
                        "requested": True,
                        "available": True,
                        "aligned": True,
                        "reason": "APPLIED",
                        "requested_metric_count": 3,
                        "requested_metrics": ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"],
                    },
                    "metrics": {"VOLATILITY": {"value": 0.23}},
                }
            }
        },
    )
    metadata: RiskResponseMetadata = Field(
        default_factory=RiskResponseMetadata,
        description="Risk contract and applied option metadata.",
        json_schema_extra={
            "example": {
                "contract_version": "v1",
                "methodology_version": "risk.v1",
                "frequency": "DAILY",
                "annualization_factor": 252,
                "use_log_returns": False,
                "risk_free_mode": "ANNUAL_RATE",
                "risk_free_annual_rate": 0.025518911987694626,
                "risk_free_context": {
                    "requested": True,
                    "applied": True,
                    "reason": "ANNUAL_RATE_APPLIED",
                    "periodic_rate": 0.0001,
                },
                "benchmark_context": {
                    "requested": True,
                    "requested_metrics": ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"],
                },
                "mar_annual_rate": 0.0,
                "var_method": "HISTORICAL",
                "var_confidence": 0.95,
                "var_horizon_days": 1,
            }
        },
    )

    model_config = ConfigDict(json_schema_extra={"example": cast(Any, RISK_RESPONSE_EXAMPLE)})
