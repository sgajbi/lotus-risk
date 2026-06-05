from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field


class RollingMetricSummary(BaseModel):
    total_point_count: int = Field(
        default=0,
        description="Total rolling observation slots evaluated for this metric/window, including null warm-up periods.",
        json_schema_extra={"example": 64},
    )
    computed_point_count: int = Field(
        default=0,
        description="Number of rolling observations that produced non-null values for this metric/window.",
        json_schema_extra={"example": 44},
    )
    coverage_ratio: float = Field(
        default=0.0,
        description="Computed-point coverage ratio for this metric/window (`computed_point_count / total_point_count`).",
        json_schema_extra={"example": 0.6875},
    )
    min_observations_required: int = Field(
        default=0,
        description="Minimum observations required before this rolling metric/window can emit non-null values.",
        json_schema_extra={"example": 21},
    )
    warmup_point_count: int = Field(
        default=0,
        description="Expected leading warm-up slots before the rolling window reaches minimum observations.",
        json_schema_extra={"example": 20},
    )
    non_computed_point_count: int = Field(
        default=0,
        description="Total slots that did not produce a rolling value for this metric/window.",
        json_schema_extra={"example": 20},
    )
    post_warmup_gap_point_count: int = Field(
        default=0,
        description="Non-computed slots beyond expected warm-up, indicating additional data/alignment gaps.",
        json_schema_extra={"example": 0},
    )
    latest_observation_date: dt.date | None = Field(
        default=None,
        description="Date of the latest non-null rolling metric value included in this summary.",
        json_schema_extra={"example": "2026-03-31"},
    )
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


class RollingBenchmarkContext(BaseModel):
    requested: bool = Field(
        description="Whether any benchmark-dependent rolling metrics were requested for this period.",
        json_schema_extra={"example": True},
    )
    available: bool = Field(
        description="Whether benchmark return observations were available in this period.",
        json_schema_extra={"example": True},
    )
    aligned: bool = Field(
        description="Whether benchmark return observations aligned with portfolio observations for requested rolling metrics.",
        json_schema_extra={"example": True},
    )
    reason: Literal[
        "NOT_REQUESTED", "BENCHMARK_UNAVAILABLE", "NO_ALIGNED_OBSERVATIONS", "APPLIED"
    ] = Field(
        description="Deterministic benchmark application outcome for the period.",
        json_schema_extra={"example": "APPLIED"},
    )


class RollingRiskFreeContext(BaseModel):
    requested: bool = Field(
        description="Whether rolling Sharpe was requested for this period.",
        json_schema_extra={"example": True},
    )
    available: bool = Field(
        description="Whether risk-free observations were available in this period.",
        json_schema_extra={"example": True},
    )
    aligned: bool = Field(
        description="Whether risk-free observations aligned with portfolio observations for rolling Sharpe.",
        json_schema_extra={"example": True},
    )
    reason: Literal[
        "NOT_REQUESTED", "RISK_FREE_UNAVAILABLE", "NO_ALIGNED_OBSERVATIONS", "APPLIED"
    ] = Field(
        description="Deterministic risk-free application outcome for the period.",
        json_schema_extra={"example": "APPLIED"},
    )
