from __future__ import annotations

import datetime as dt

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


__all__ = ["RollingMetricSummary"]
