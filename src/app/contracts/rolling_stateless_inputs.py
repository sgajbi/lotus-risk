from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.contracts.risk import ReturnPoint, RiskRequestPeriod, RiskRequestScope
from app.contracts.rolling_common_inputs import (
    ROLLING_BENCHMARK_METRICS,
    ROLLING_MAX_PERIODS,
    ROLLING_MAX_STATELESS_OBSERVATIONS,
    RollingMetric,
    RollingOptions,
    validate_rolling_time_series_workload,
    validate_unique_period_names,
)


def validate_rolling_stateless_dependencies(
    *,
    requested_metrics: set[RollingMetric],
    benchmark_returns: list[ReturnPoint],
    risk_free_returns: list[ReturnPoint],
) -> None:
    if requested_metrics.intersection(ROLLING_BENCHMARK_METRICS) and not benchmark_returns:
        raise ValueError(
            "benchmark_returns are required when requesting rolling benchmark-dependent metrics"
        )
    if "ROLLING_SHARPE" in requested_metrics and not risk_free_returns:
        raise ValueError("risk_free_returns are required when requesting ROLLING_SHARPE")


class RollingStatelessInput(BaseModel):
    scope: RiskRequestScope = Field(
        description="Scope and policy context for rolling risk calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    periods: list[RiskRequestPeriod] = Field(
        description="List of periods to evaluate rolling metrics.",
        max_length=ROLLING_MAX_PERIODS,
        json_schema_extra={"example": [{"type": "YTD", "name": "YTD"}]},
    )
    returns: list[ReturnPoint] = Field(
        description="Portfolio return observations in percentage points.",
        max_length=ROLLING_MAX_STATELESS_OBSERVATIONS,
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.45}]},
    )
    benchmark_returns: list[ReturnPoint] = Field(
        default_factory=list,
        description="Benchmark return observations in percentage points required for benchmark metrics.",
        max_length=ROLLING_MAX_STATELESS_OBSERVATIONS,
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.32}]},
    )
    risk_free_returns: list[ReturnPoint] = Field(
        default_factory=list,
        description="Risk-free return observations in percentage points required for rolling Sharpe.",
        max_length=ROLLING_MAX_STATELESS_OBSERVATIONS,
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.01}]},
    )
    rolling_options: RollingOptions = Field(
        default_factory=RollingOptions,
        description="Rolling metric configuration options.",
        json_schema_extra={
            "example": {
                "window_lengths": [21, 63, 126],
                "metrics": [
                    "ROLLING_VOLATILITY",
                    "ROLLING_SHARPE",
                    "ROLLING_BETA",
                    "ROLLING_TRACKING_ERROR",
                ],
                "annualization_basis": 252,
                "min_observations_policy": "STRICT",
                "alignment_policy": "INNER_JOIN",
                "include_time_series": False,
            }
        },
    )

    @model_validator(mode="after")
    def validate_semantics(self) -> "RollingStatelessInput":
        validate_unique_period_names(self.periods)
        validate_rolling_time_series_workload(
            period_count=len(self.periods),
            window_count=len(self.rolling_options.window_lengths),
            observation_count=len(self.returns),
            include_time_series=self.rolling_options.include_time_series,
        )
        validate_rolling_stateless_dependencies(
            requested_metrics=set(self.rolling_options.metrics),
            benchmark_returns=self.benchmark_returns,
            risk_free_returns=self.risk_free_returns,
        )
        return self


__all__ = [
    "RollingStatelessInput",
    "validate_rolling_stateless_dependencies",
]
