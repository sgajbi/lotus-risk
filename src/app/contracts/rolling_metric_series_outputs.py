from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.rolling_metric_summary_outputs import RollingMetricSummary


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


class RollingMetricSeriesContext(BaseModel):
    requested: bool = Field(
        description="Whether rolling time-series points were requested for this window.",
        json_schema_extra={"example": True},
    )
    included: bool = Field(
        description="Whether rolling time-series points are included in the response for this window.",
        json_schema_extra={"example": True},
    )
    emitted_point_count: int = Field(
        default=0,
        description="Number of time-series points emitted for this window.",
        json_schema_extra={"example": 64},
    )
    reason: Literal["INCLUDED", "OMITTED_BY_REQUEST", "NO_METRIC_SERIES"] = Field(
        description="Deterministic reason for time-series inclusion behavior in this window.",
        json_schema_extra={"example": "INCLUDED"},
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
                    "total_point_count": 64,
                    "computed_point_count": 44,
                    "coverage_ratio": 0.6875,
                    "min_observations_required": 21,
                    "warmup_point_count": 20,
                    "non_computed_point_count": 20,
                    "post_warmup_gap_point_count": 0,
                    "latest_observation_date": "2026-03-31",
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
    metric_series_context: RollingMetricSeriesContext = Field(
        description="Time-series inclusion context for this rolling window.",
        json_schema_extra={
            "example": {
                "requested": True,
                "included": True,
                "emitted_point_count": 64,
                "reason": "INCLUDED",
            }
        },
    )


__all__ = [
    "RollingMetricSeriesContext",
    "RollingMetricSeriesPoint",
    "RollingWindowResult",
]
