from __future__ import annotations

import datetime as dt
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.audit import AuditMetadataFields
from app.contracts.drawdown_examples import DRAWDOWN_RESPONSE_EXAMPLES
from app.contracts.drawdown_inputs import DrawdownInputMode
from app.contracts.risk import RiskCalculationSupportability, RiskRequestScope


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


class DrawdownPeriodResult(BaseModel):
    start_date: dt.date = Field(
        description="Resolved period start date.",
        json_schema_extra={"example": "2026-01-01"},
    )
    end_date: dt.date = Field(
        description="Resolved period end date.",
        json_schema_extra={"example": "2026-02-28"},
    )
    portfolio_observation_count: int = Field(
        default=0,
        description="Number of portfolio return observations included in this period result.",
        json_schema_extra={"example": 90},
    )
    benchmark_observation_count: int = Field(
        default=0,
        description="Number of benchmark return observations available in this period result.",
        json_schema_extra={"example": 90},
    )
    summary: DrawdownSummary | None = Field(
        default=None,
        description="Summary drawdown metrics for this period.",
        json_schema_extra={"example": {"max_drawdown": -0.124533}},
    )
    episodes: list[DrawdownEpisode] = Field(
        default_factory=list,
        description="Worst drawdown episodes retained by policy filters.",
        json_schema_extra={
            "example": [
                {
                    "episode_id": "dd_0001",
                    "peak_date": "2026-01-12",
                    "trough_date": "2026-02-03",
                    "recovery_date": None,
                    "depth": -0.124533,
                    "days_to_trough": 16,
                    "days_to_recovery": None,
                    "total_days": 34,
                    "is_recovered": False,
                }
            ]
        },
    )
    relative_to_benchmark: RelativeDrawdownSummary | None = Field(
        default=None,
        description="Optional benchmark-relative drawdown summary.",
        json_schema_extra={
            "example": {
                "max_drawdown": -0.0821,
                "max_drawdown_peak_date": "2026-01-11",
                "max_drawdown_trough_date": "2026-02-01",
                "max_drawdown_recovery_date": "2026-02-18",
                "is_recovered": True,
                "days_to_trough": 15,
                "days_to_recovery": 9,
                "time_under_water_days": 21,
            }
        },
    )
    relative_to_benchmark_context: RelativeDrawdownContext = Field(
        default_factory=RelativeDrawdownContext,
        description=(
            "Execution context for benchmark-relative drawdown, including whether it was "
            "requested and whether aligned benchmark observations were available."
        ),
        json_schema_extra={
            "example": {
                "requested": True,
                "applied": True,
                "reason": "APPLIED",
                "aligned_observation_count": 64,
            }
        },
    )
    underwater_series: list[UnderwaterPoint] | None = Field(
        default=None,
        description="Optional underwater drawdown series points.",
        json_schema_extra={"example": [{"date": "2026-01-20", "drawdown": -0.0521}]},
    )
    error: str | None = Field(
        default=None,
        description="Deterministic period-level error when drawdown summary cannot be computed.",
        json_schema_extra={"example": "Insufficient data"},
    )


class DrawdownMetadata(AuditMetadataFields):
    contract_version: str = Field(
        default="v1",
        description="Drawdown analytics contract version.",
        json_schema_extra={"example": "v1"},
    )
    methodology_version: str = Field(
        default="drawdown.v1",
        description="Methodology version used for drawdown analytics formulas.",
        json_schema_extra={"example": "drawdown.v1"},
    )
    include_underwater_series: bool = Field(
        default=False,
        description="Whether underwater drawdown series was included in period results.",
        json_schema_extra={"example": False},
    )
    include_episode_list: bool = Field(
        default=True,
        description="Whether drawdown episode lists were included in period results.",
        json_schema_extra={"example": True},
    )
    top_n_episodes: int = Field(
        default=5,
        description="Maximum number of worst drawdown episodes retained per period.",
        json_schema_extra={"example": 5},
    )
    cdar_alpha: float = Field(
        default=0.95,
        description="Confidence level used for drawdown-at-risk and conditional drawdown-at-risk.",
        json_schema_extra={"example": 0.95},
    )
    minimum_episode_depth_bps: float = Field(
        default=0.0,
        description="Minimum episode depth threshold, in basis points, applied to episode lists.",
        json_schema_extra={"example": 25.0},
    )
    duration_unit: Literal["BUSINESS_DAYS", "CALENDAR_DAYS"] = Field(
        default="BUSINESS_DAYS",
        description="Duration convention applied to episode timing fields.",
        json_schema_extra={"example": "BUSINESS_DAYS"},
    )
    include_benchmark: bool | None = Field(
        default=None,
        description="Whether benchmark-relative drawdown was requested.",
        json_schema_extra={"example": True},
    )
    missing_benchmark_policy: Literal["IGNORE", "REQUIRE"] | None = Field(
        default=None,
        description="Behavior requested when benchmark series is unavailable.",
        json_schema_extra={"example": "IGNORE"},
    )
    calculation_supportability: RiskCalculationSupportability = Field(
        default_factory=lambda: RiskCalculationSupportability(
            state="ready",
            reason="calculation_complete",
            freshness_bucket="unknown",
        ),
        description="Source-backed supportability posture for UI and operator consumption.",
        json_schema_extra={
            "example": {
                "state": "ready",
                "reason": "calculation_complete",
                "freshness_bucket": "current",
                "degraded_metric_count": 0,
                "empty_period_count": 0,
                "evaluated_period_count": 1,
            }
        },
    )


class DrawdownResponse(BaseModel):
    source_service: Literal["lotus-risk"] = Field(
        default="lotus-risk",
        description="Service identifier producing this drawdown analytics response.",
        json_schema_extra={"example": "lotus-risk"},
    )
    input_mode: DrawdownInputMode = Field(
        description="Execution mode used to produce this response.",
        json_schema_extra={"example": "stateful"},
    )
    scope: RiskRequestScope = Field(
        description="Normalized scope context used for drawdown calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    results: dict[str, DrawdownPeriodResult] = Field(
        description="Drawdown period results keyed by period name.",
        json_schema_extra={
            "example": {
                "YTD": {
                    "start_date": "2026-01-01",
                    "end_date": "2026-03-31",
                    "summary": {
                        "max_drawdown": -0.084211,
                        "max_drawdown_peak_date": "2026-01-11",
                        "max_drawdown_trough_date": "2026-02-03",
                    },
                    "episodes": [
                        {
                            "episode_id": "dd_0001",
                            "peak_date": "2026-01-11",
                            "trough_date": "2026-02-03",
                            "recovery_date": "2026-02-19",
                            "depth": -0.084211,
                            "days_to_trough": 16,
                            "days_to_recovery": 11,
                            "total_days": 27,
                            "is_recovered": True,
                        }
                    ],
                    "relative_to_benchmark": {
                        "max_drawdown": -0.026414,
                        "max_drawdown_peak_date": "2026-01-04",
                        "max_drawdown_trough_date": "2026-02-15",
                        "time_under_water_days": 74,
                    },
                    "underwater_series": [{"date": "2026-01-02", "drawdown": -0.0121}],
                    "error": None,
                }
            }
        },
    )
    metadata: DrawdownMetadata = Field(
        default_factory=DrawdownMetadata,
        description="Drawdown contract and methodology metadata.",
        json_schema_extra={
            "example": {
                "contract_version": "v1",
                "methodology_version": "drawdown.v1",
                "include_underwater_series": False,
                "include_episode_list": True,
                "top_n_episodes": 5,
                "cdar_alpha": 0.95,
                "minimum_episode_depth_bps": 0.0,
                "duration_unit": "BUSINESS_DAYS",
                "include_benchmark": True,
                "missing_benchmark_policy": "IGNORE",
            }
        },
    )

    model_config = ConfigDict(json_schema_extra={"examples": cast(Any, DRAWDOWN_RESPONSE_EXAMPLES)})
