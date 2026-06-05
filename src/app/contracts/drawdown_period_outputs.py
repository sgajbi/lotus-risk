from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.contracts.drawdown_metric_outputs import (
    DrawdownEpisode,
    DrawdownSummary,
    RelativeDrawdownContext,
    RelativeDrawdownSummary,
    UnderwaterPoint,
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


__all__ = ["DrawdownPeriodResult"]
