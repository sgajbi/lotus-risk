from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.audit import AuditMetadataFields
from app.contracts.risk_examples import RISK_RESPONSE_EXAMPLE
from app.contracts.risk_inputs import RiskRequestScope
from app.contracts.risk_metric_outputs import RiskPeriodResult
from app.contracts.risk_response_contexts import (
    BenchmarkRequestContext,
    RiskCalculationSupportability,
    RiskFreeContext,
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


__all__ = [
    "RiskResponse",
    "RiskResponseMetadata",
]
