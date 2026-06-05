from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field


class DrawdownEpisode(BaseModel):
    episode_id: str = Field(
        description="Stable drawdown episode identifier for this period response.",
        json_schema_extra={"example": "dd_0001"},
    )
    peak_date: dt.date = Field(
        description="Episode peak date before drawdown started.",
        json_schema_extra={"example": "2026-01-12"},
    )
    trough_date: dt.date = Field(
        description="Episode trough date at maximum episode depth.",
        json_schema_extra={"example": "2026-02-03"},
    )
    recovery_date: dt.date | None = Field(
        default=None,
        description="Recovery date when wealth index returned to prior peak, if recovered.",
        json_schema_extra={"example": "2026-02-19"},
    )
    depth: float = Field(
        description="Episode depth in decimal drawdown units (negative values).",
        json_schema_extra={"example": -0.124533},
    )
    days_to_trough: int = Field(
        description="Number of duration-unit days from peak to trough.",
        json_schema_extra={"example": 16},
    )
    days_to_recovery: int | None = Field(
        default=None,
        description="Number of duration-unit days from trough to recovery, if recovered.",
        json_schema_extra={"example": 11},
    )
    total_days: int = Field(
        description="Total duration-unit days from peak to recovery (or period end if unrecovered).",
        json_schema_extra={"example": 34},
    )
    is_recovered: bool = Field(
        description="Whether this episode recovered before period end.",
        json_schema_extra={"example": False},
    )


class UnderwaterPoint(BaseModel):
    date: dt.date = Field(
        description="Observation date in the underwater series.",
        json_schema_extra={"example": "2026-01-20"},
    )
    drawdown: float = Field(
        description="Drawdown value in decimal units for this date.",
        json_schema_extra={"example": -0.0521},
    )


class DrawdownSummary(BaseModel):
    max_drawdown: float | None = Field(
        description="Maximum drawdown over the period in decimal units (negative values).",
        json_schema_extra={"example": -0.124533},
    )
    max_drawdown_peak_date: dt.date | None = Field(
        default=None,
        description="Peak date associated with maximum drawdown.",
        json_schema_extra={"example": "2026-01-12"},
    )
    max_drawdown_trough_date: dt.date | None = Field(
        default=None,
        description="Trough date associated with maximum drawdown.",
        json_schema_extra={"example": "2026-02-03"},
    )
    max_drawdown_recovery_date: dt.date | None = Field(
        default=None,
        description="Recovery date for maximum drawdown, if recovered.",
        json_schema_extra={"example": "2026-02-19"},
    )
    is_recovered: bool = Field(
        description="Whether the maximum drawdown episode recovered before period end.",
        json_schema_extra={"example": False},
    )
    days_to_trough: int | None = Field(
        default=None,
        description="Duration-unit days from peak to trough for maximum drawdown episode.",
        json_schema_extra={"example": 16},
    )
    days_to_recovery: int | None = Field(
        default=None,
        description="Duration-unit days from trough to recovery for maximum drawdown episode.",
        json_schema_extra={"example": 11},
    )
    time_under_water_days: int = Field(
        description=(
            "Number of portfolio return observations in the period where drawdown was below zero. "
            "This is observation-based and is not affected by duration_unit."
        ),
        json_schema_extra={"example": 34},
    )
    average_drawdown: float | None = Field(
        default=None,
        description="Average drawdown across underwater observations in decimal units.",
        json_schema_extra={"example": -0.041208},
    )
    ulcer_index: float | None = Field(
        default=None,
        description="Ulcer index over period drawdown path in decimal units.",
        json_schema_extra={"example": 0.053901},
    )
    drawdown_at_risk_95: float | None = Field(
        default=None,
        description="Drawdown-at-risk using configured alpha at episode depth quantile.",
        json_schema_extra={"example": -0.101552},
    )
    conditional_drawdown_at_risk_95: float | None = Field(
        default=None,
        description="Conditional drawdown-at-risk for worst episode tail at configured alpha.",
        json_schema_extra={"example": -0.117884},
    )


class RelativeDrawdownSummary(BaseModel):
    max_drawdown: float | None = Field(
        description="Maximum drawdown of active (portfolio minus benchmark) return path.",
        json_schema_extra={"example": -0.0842},
    )
    max_drawdown_peak_date: dt.date | None = Field(
        default=None,
        description="Peak date associated with relative maximum drawdown.",
        json_schema_extra={"example": "2026-01-11"},
    )
    max_drawdown_trough_date: dt.date | None = Field(
        default=None,
        description="Trough date associated with relative maximum drawdown.",
        json_schema_extra={"example": "2026-02-01"},
    )
    max_drawdown_recovery_date: dt.date | None = Field(
        default=None,
        description="Recovery date for the relative maximum drawdown episode, if recovered.",
        json_schema_extra={"example": "2026-02-18"},
    )
    is_recovered: bool = Field(
        default=False,
        description="Whether the relative maximum drawdown episode recovered before period end.",
        json_schema_extra={"example": True},
    )
    days_to_trough: int | None = Field(
        default=None,
        description="Number of duration-unit days from relative peak to trough.",
        json_schema_extra={"example": 15},
    )
    days_to_recovery: int | None = Field(
        default=None,
        description="Number of duration-unit days from relative trough to recovery, if recovered.",
        json_schema_extra={"example": 9},
    )
    time_under_water_days: int = Field(
        default=0,
        description=(
            "Number of aligned active-return observations where active drawdown remained below "
            "zero. This is observation-based and is not affected by duration_unit."
        ),
        json_schema_extra={"example": 21},
    )


class RelativeDrawdownContext(BaseModel):
    requested: bool = Field(
        default=False,
        description="Whether benchmark-relative drawdown was requested for this period.",
        json_schema_extra={"example": True},
    )
    applied: bool = Field(
        default=False,
        description="Whether benchmark-relative drawdown was actually computed for this period.",
        json_schema_extra={"example": True},
    )
    reason: Literal[
        "NOT_REQUESTED",
        "BENCHMARK_UNAVAILABLE",
        "NO_ALIGNED_OBSERVATIONS",
        "APPLIED",
    ] = Field(
        default="NOT_REQUESTED",
        description="Deterministic reason explaining whether benchmark-relative drawdown was applied.",
        json_schema_extra={"example": "APPLIED"},
    )
    aligned_observation_count: int = Field(
        default=0,
        description="Number of aligned portfolio and benchmark observations used for relative drawdown.",
        json_schema_extra={"example": 64},
    )
