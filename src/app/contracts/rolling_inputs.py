from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.risk import ReturnPoint, RiskRequestPeriod, RiskRequestScope


class RollingInputMode(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"


RollingMetric = Literal[
    "ROLLING_VOLATILITY",
    "ROLLING_SHARPE",
    "ROLLING_BETA",
    "ROLLING_TRACKING_ERROR",
    "ROLLING_INFORMATION_RATIO",
    "ROLLING_MAX_DRAWDOWN",
]


ROLLING_BENCHMARK_METRICS: set[str] = {
    "ROLLING_BETA",
    "ROLLING_TRACKING_ERROR",
    "ROLLING_INFORMATION_RATIO",
}


def _default_rolling_metrics() -> list[RollingMetric]:
    return [
        "ROLLING_VOLATILITY",
        "ROLLING_SHARPE",
        "ROLLING_BETA",
        "ROLLING_TRACKING_ERROR",
        "ROLLING_INFORMATION_RATIO",
        "ROLLING_MAX_DRAWDOWN",
    ]


def _validate_unique_period_names(periods: list[RiskRequestPeriod]) -> None:
    resolved_names = [period.name or period.type for period in periods]
    duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
    if duplicates:
        raise ValueError(
            "Duplicate period names resolved in request: "
            + ", ".join(duplicates)
            + ". Each period name (or type fallback) must be unique."
        )


def _validate_rolling_stateless_dependencies(
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


class RollingOptions(BaseModel):
    window_lengths: list[int] = Field(
        default_factory=lambda: [21, 63, 126, 252],
        description="Rolling window lengths in observations.",
        json_schema_extra={"example": [21, 63, 126, 252]},
    )
    metrics: list[RollingMetric] = Field(
        default_factory=_default_rolling_metrics,
        description="Requested rolling metrics.",
        json_schema_extra={
            "example": [
                "ROLLING_VOLATILITY",
                "ROLLING_SHARPE",
                "ROLLING_BETA",
                "ROLLING_TRACKING_ERROR",
                "ROLLING_INFORMATION_RATIO",
                "ROLLING_MAX_DRAWDOWN",
            ]
        },
    )
    annualization_basis: int = Field(
        default=252,
        ge=1,
        description="Annualization basis used by annualized rolling metrics.",
        json_schema_extra={"example": 252},
    )
    min_observations_policy: Literal["STRICT", "ALLOW_PARTIAL"] = Field(
        default="STRICT",
        description="Policy for minimum observations per rolling window.",
        json_schema_extra={"example": "STRICT"},
    )
    alignment_policy: Literal["INNER_JOIN"] = Field(
        default="INNER_JOIN",
        description="Series alignment policy used for multi-series rolling metrics.",
        json_schema_extra={"example": "INNER_JOIN"},
    )
    include_time_series: bool = Field(
        default=False,
        description="Whether rolling metric time-series points should be included in each window result.",
        json_schema_extra={"example": False},
    )

    @model_validator(mode="after")
    def validate_window_lengths(self) -> "RollingOptions":
        if not self.window_lengths:
            raise ValueError("window_lengths must contain at least one window")
        if any(window <= 1 for window in self.window_lengths):
            raise ValueError("window_lengths must be greater than 1")
        if len(set(self.window_lengths)) != len(self.window_lengths):
            raise ValueError("window_lengths must be unique")
        return self


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
        json_schema_extra={"example": [{"type": "YTD", "name": "YTD"}]},
    )
    returns: list[ReturnPoint] = Field(
        description="Portfolio return observations in percentage points.",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.45}]},
    )
    benchmark_returns: list[ReturnPoint] = Field(
        default_factory=list,
        description="Benchmark return observations in percentage points required for benchmark metrics.",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.32}]},
    )
    risk_free_returns: list[ReturnPoint] = Field(
        default_factory=list,
        description="Risk-free return observations in percentage points required for rolling Sharpe.",
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
        _validate_unique_period_names(self.periods)
        _validate_rolling_stateless_dependencies(
            requested_metrics=set(self.rolling_options.metrics),
            benchmark_returns=self.benchmark_returns,
            risk_free_returns=self.risk_free_returns,
        )
        return self


class RollingStatefulInput(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier resolved through lotus-performance integration contracts.",
        json_schema_extra={"example": "DEMO_DPM_EUR_001"},
    )
    as_of_date: dt.date = Field(
        description="Business date used for upstream series sourcing.",
        json_schema_extra={"example": "2026-02-28"},
    )
    client_id: str | None = Field(
        default=None,
        description="Optional client identifier for policy-controlled upstream access.",
        json_schema_extra={"example": "CLIENT_1000123"},
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Optional reporting currency override.",
        json_schema_extra={"example": "USD"},
    )
    net_or_gross: Literal["NET", "GROSS"] = Field(
        default="NET",
        description="Whether sourced returns are net or gross.",
        json_schema_extra={"example": "NET"},
    )
    periods: list[RiskRequestPeriod] = Field(
        description="List of periods to evaluate rolling metrics.",
        json_schema_extra={"example": [{"type": "YTD", "name": "YTD"}]},
    )
    rolling_options: RollingOptions = Field(
        default_factory=RollingOptions,
        description="Rolling metric configuration options.",
        json_schema_extra={
            "example": {
                "window_lengths": [21, 63, 126],
                "metrics": ["ROLLING_VOLATILITY", "ROLLING_MAX_DRAWDOWN"],
                "annualization_basis": 252,
                "min_observations_policy": "STRICT",
                "alignment_policy": "INNER_JOIN",
                "include_time_series": False,
            }
        },
    )

    @model_validator(mode="after")
    def validate_semantics(self) -> "RollingStatefulInput":
        _validate_unique_period_names(self.periods)
        return self


class RollingAnalyticsRequest(BaseModel):
    input_mode: RollingInputMode = Field(
        default=RollingInputMode.STATELESS,
        description="Execution mode for rolling risk analytics.",
        json_schema_extra={"example": "stateless"},
    )
    stateless_input: RollingStatelessInput | None = Field(
        default=None,
        description="Stateless payload with fully supplied return series.",
        json_schema_extra={
            "example": {
                "scope": {"as_of_date": "2026-02-28", "net_or_gross": "NET"},
                "periods": [{"type": "YTD", "name": "YTD"}],
                "returns": [{"date": "2026-01-02", "value": 0.45}],
                "benchmark_returns": [{"date": "2026-01-02", "value": 0.32}],
                "risk_free_returns": [{"date": "2026-01-02", "value": 0.01}],
            }
        },
    )
    stateful_input: RollingStatefulInput | None = Field(
        default=None,
        description=(
            "Stateful payload sourced through lotus-performance for portfolio/benchmark returns "
            "and lotus-core for risk-free reference series when rolling Sharpe is requested."
        ),
        json_schema_extra={
            "example": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-28",
                "periods": [{"type": "YTD", "name": "YTD"}],
                "rolling_options": {
                    "window_lengths": [21, 63],
                    "metrics": [
                        "ROLLING_VOLATILITY",
                        "ROLLING_BETA",
                        "ROLLING_TRACKING_ERROR",
                    ],
                    "annualization_basis": 252,
                    "min_observations_policy": "STRICT",
                    "alignment_policy": "INNER_JOIN",
                    "include_time_series": False,
                },
            }
        },
    )
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "RollingAnalyticsRequest":
        if self.input_mode == RollingInputMode.STATELESS and self.stateless_input is None:
            raise ValueError("stateless_input is required when input_mode=stateless")
        if self.input_mode == RollingInputMode.STATEFUL and self.stateful_input is None:
            raise ValueError("stateful_input is required when input_mode=stateful")
        return self
