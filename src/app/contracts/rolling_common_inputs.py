from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.risk import RiskRequestPeriod

ROLLING_MAX_PERIODS = 12
ROLLING_MAX_STATELESS_OBSERVATIONS = 2500
ROLLING_MAX_TIME_SERIES_POINTS = 10000
ROLLING_MAX_WINDOW_COUNT = 8
ROLLING_MAX_WINDOW_LENGTH = 756


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


def validate_unique_period_names(periods: list[RiskRequestPeriod]) -> None:
    resolved_names = [period.name or period.type for period in periods]
    duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
    if duplicates:
        raise ValueError(
            "Duplicate period names resolved in request: "
            + ", ".join(duplicates)
            + ". Each period name (or type fallback) must be unique."
        )


def validate_rolling_time_series_workload(
    *,
    period_count: int,
    window_count: int,
    observation_count: int,
    include_time_series: bool,
) -> None:
    if not include_time_series:
        return
    projected_points = period_count * window_count * observation_count
    if projected_points > ROLLING_MAX_TIME_SERIES_POINTS:
        raise ValueError(
            "include_time_series workload exceeds supported maximum "
            f"{ROLLING_MAX_TIME_SERIES_POINTS} emitted points"
        )


class RollingOptions(BaseModel):
    window_lengths: list[int] = Field(
        default_factory=lambda: [21, 63, 126, 252],
        description="Rolling window lengths in observations.",
        max_length=ROLLING_MAX_WINDOW_COUNT,
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
        if any(window > ROLLING_MAX_WINDOW_LENGTH for window in self.window_lengths):
            raise ValueError(
                f"window_lengths must be less than or equal to {ROLLING_MAX_WINDOW_LENGTH}"
            )
        if len(set(self.window_lengths)) != len(self.window_lengths):
            raise ValueError("window_lengths must be unique")
        return self


__all__ = [
    "ROLLING_BENCHMARK_METRICS",
    "ROLLING_MAX_PERIODS",
    "ROLLING_MAX_STATELESS_OBSERVATIONS",
    "ROLLING_MAX_TIME_SERIES_POINTS",
    "ROLLING_MAX_WINDOW_COUNT",
    "ROLLING_MAX_WINDOW_LENGTH",
    "RollingInputMode",
    "RollingMetric",
    "RollingOptions",
    "validate_rolling_time_series_workload",
    "validate_unique_period_names",
]
