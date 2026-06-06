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
from app.contracts.drawdown_period_field_examples import (
    DRAWDOWN_PERIOD_EPISODES_EXAMPLE,
    DRAWDOWN_PERIOD_RELATIVE_CONTEXT_EXAMPLE,
    DRAWDOWN_PERIOD_RELATIVE_TO_BENCHMARK_EXAMPLE,
    DRAWDOWN_PERIOD_SUMMARY_EXAMPLE,
    DRAWDOWN_PERIOD_UNDERWATER_SERIES_EXAMPLE,
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
        json_schema_extra={"example": DRAWDOWN_PERIOD_SUMMARY_EXAMPLE},
    )
    episodes: list[DrawdownEpisode] = Field(
        default_factory=list,
        description="Worst drawdown episodes retained by policy filters.",
        json_schema_extra={"example": DRAWDOWN_PERIOD_EPISODES_EXAMPLE},
    )
    relative_to_benchmark: RelativeDrawdownSummary | None = Field(
        default=None,
        description="Optional benchmark-relative drawdown summary.",
        json_schema_extra={"example": DRAWDOWN_PERIOD_RELATIVE_TO_BENCHMARK_EXAMPLE},
    )
    relative_to_benchmark_context: RelativeDrawdownContext = Field(
        default_factory=RelativeDrawdownContext,
        description=(
            "Execution context for benchmark-relative drawdown, including whether it was "
            "requested and whether aligned benchmark observations were available."
        ),
        json_schema_extra={"example": DRAWDOWN_PERIOD_RELATIVE_CONTEXT_EXAMPLE},
    )
    underwater_series: list[UnderwaterPoint] | None = Field(
        default=None,
        description="Optional underwater drawdown series points.",
        json_schema_extra={"example": DRAWDOWN_PERIOD_UNDERWATER_SERIES_EXAMPLE},
    )
    error: str | None = Field(
        default=None,
        description="Deterministic period-level error when drawdown summary cannot be computed.",
        json_schema_extra={"example": "Insufficient data"},
    )


__all__ = ["DrawdownPeriodResult"]
