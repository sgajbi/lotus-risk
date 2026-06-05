from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.risk import RiskRequestPeriod


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


__all__ = [
    "ROLLING_BENCHMARK_METRICS",
    "RollingInputMode",
    "RollingMetric",
    "RollingOptions",
    "validate_unique_period_names",
]
