from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


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


__all__ = [
    "RiskPeriodResult",
    "RiskValue",
]
