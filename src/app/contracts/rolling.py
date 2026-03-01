from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.risk import ReturnPoint, RiskRequestPeriod, RiskRequestScope


class RollingInputMode(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"
    SIMULATION = "simulation"


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
        resolved_names = [period.name or period.type for period in self.periods]
        duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
        if duplicates:
            raise ValueError(
                "Duplicate period names resolved in request: "
                + ", ".join(duplicates)
                + ". Each period name (or type fallback) must be unique."
            )

        requested_metrics = set(self.rolling_options.metrics)
        if requested_metrics.intersection(ROLLING_BENCHMARK_METRICS) and not self.benchmark_returns:
            raise ValueError(
                "benchmark_returns are required when requesting rolling benchmark-dependent metrics"
            )
        if "ROLLING_SHARPE" in requested_metrics and not self.risk_free_returns:
            raise ValueError("risk_free_returns are required when requesting ROLLING_SHARPE")
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
        description="Stateful payload sourced through lotus-performance integrations (future slice).",
        json_schema_extra={
            "example": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-28",
                "periods": [{"type": "YTD", "name": "YTD"}],
            }
        },
    )
    simulation_input: RollingStatefulInput | None = Field(
        default=None,
        description="Simulation payload. Reserved for a future slice.",
        json_schema_extra={
            "example": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-28",
                "periods": [{"type": "YTD", "name": "YTD"}],
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
        if self.input_mode == RollingInputMode.SIMULATION and self.simulation_input is None:
            raise ValueError("simulation_input is required when input_mode=simulation")
        return self


class RollingMetricSummary(BaseModel):
    latest: float | None = Field(
        default=None,
        description="Latest rolling metric value in decimal units for this period/window.",
        json_schema_extra={"example": 0.1374},
    )
    average: float | None = Field(
        default=None,
        description="Average rolling metric value over the period/window.",
        json_schema_extra={"example": 0.1221},
    )
    minimum: float | None = Field(
        default=None,
        description="Minimum rolling metric value over the period/window.",
        json_schema_extra={"example": 0.0913},
    )
    maximum: float | None = Field(
        default=None,
        description="Maximum rolling metric value over the period/window.",
        json_schema_extra={"example": 0.1662},
    )
    p05: float | None = Field(
        default=None,
        description="5th percentile rolling metric value over the period/window.",
        json_schema_extra={"example": 0.0975},
    )
    p50: float | None = Field(
        default=None,
        description="50th percentile rolling metric value over the period/window.",
        json_schema_extra={"example": 0.1218},
    )
    p95: float | None = Field(
        default=None,
        description="95th percentile rolling metric value over the period/window.",
        json_schema_extra={"example": 0.1611},
    )


class RollingMetricSeriesPoint(BaseModel):
    date: dt.date = Field(
        description="Observation date for rolling metric values.",
        json_schema_extra={"example": "2026-02-28"},
    )
    metric_values: dict[str, float | None] = Field(
        description="Rolling metric values keyed by metric name for this date.",
        json_schema_extra={
            "example": {
                "ROLLING_VOLATILITY": 0.1374,
                "ROLLING_SHARPE": 0.8123,
            }
        },
    )


class RollingWindowResult(BaseModel):
    window_length: int = Field(
        description="Rolling window length in observations.",
        json_schema_extra={"example": 63},
    )
    metric_summaries: dict[str, RollingMetricSummary] = Field(
        description="Rolling metric summaries keyed by metric name.",
        json_schema_extra={
            "example": {
                "ROLLING_VOLATILITY": {
                    "latest": 0.1374,
                    "average": 0.1221,
                    "minimum": 0.0913,
                    "maximum": 0.1662,
                    "p05": 0.0975,
                    "p50": 0.1218,
                    "p95": 0.1611,
                }
            }
        },
    )
    metric_series: list[RollingMetricSeriesPoint] | None = Field(
        default=None,
        description="Optional rolling metric time series for this window.",
        json_schema_extra={
            "example": [
                {
                    "date": "2026-02-28",
                    "metric_values": {
                        "ROLLING_VOLATILITY": 0.1374,
                        "ROLLING_SHARPE": 0.8123,
                    },
                }
            ]
        },
    )


class RollingPeriodResult(BaseModel):
    start_date: dt.date = Field(
        description="Resolved period start date.",
        json_schema_extra={"example": "2026-01-01"},
    )
    end_date: dt.date = Field(
        description="Resolved period end date.",
        json_schema_extra={"example": "2026-02-28"},
    )
    series_count: int = Field(
        description="Number of portfolio return observations used in this period.",
        json_schema_extra={"example": 41},
    )
    window_results: list[RollingWindowResult] = Field(
        default_factory=list,
        description="Rolling window results for this period.",
        json_schema_extra={"example": [{"window_length": 63, "metric_summaries": {}}]},
    )
    quality_flags: list[str] = Field(
        default_factory=list,
        description="Deterministic quality/coverage flags for this period.",
        json_schema_extra={"example": ["metric:ROLLING_BETA:benchmark_variance_zero"]},
    )
    error: str | None = Field(
        default=None,
        description="Deterministic period-level error when rolling metrics cannot be computed.",
        json_schema_extra={"example": "Insufficient data"},
    )


class RollingMetadata(BaseModel):
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
    alignment_policy: Literal["INNER_JOIN"] = Field(
        description="Series alignment policy used for multi-series rolling metrics.",
        json_schema_extra={"example": "INNER_JOIN"},
    )


class RollingResponse(BaseModel):
    source_service: Literal["lotus-risk"] = Field(
        default="lotus-risk",
        description="Service identifier producing this rolling analytics response.",
        json_schema_extra={"example": "lotus-risk"},
    )
    input_mode: RollingInputMode = Field(
        description="Execution mode used to produce this response.",
        json_schema_extra={"example": "stateless"},
    )
    scope: RiskRequestScope = Field(
        description="Normalized scope context used for rolling calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    results: dict[str, RollingPeriodResult] = Field(
        description="Rolling metric period results keyed by period name.",
        json_schema_extra={
            "example": {
                "YTD": {
                    "start_date": "2026-01-01",
                    "end_date": "2026-02-28",
                    "series_count": 41,
                    "window_results": [],
                    "quality_flags": [],
                    "error": None,
                }
            }
        },
    )
    metadata: RollingMetadata = Field(
        description="Rolling metric contract and methodology metadata.",
        json_schema_extra={
            "example": {
                "contract_version": "v1",
                "methodology_version": "rolling_metrics.v1",
                "annualization_basis": 252,
                "alignment_policy": "INNER_JOIN",
            }
        },
    )
