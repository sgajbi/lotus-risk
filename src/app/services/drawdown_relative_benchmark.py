from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownSummary,
    RelativeDrawdownContext,
    RelativeDrawdownSummary,
)
from app.services.drawdown_series import (
    drawdown_from_returns as _drawdown_from_returns,
    drawdown_summary as _drawdown_summary,
)


@dataclass(frozen=True)
class RelativeBenchmarkSeries:
    portfolio_returns: pd.Series
    benchmark_returns: pd.Series
    benchmark_available: bool


@dataclass(frozen=True)
class RelativeBenchmarkResult:
    summary: RelativeDrawdownSummary | None
    context: RelativeDrawdownContext


def relative_benchmark_result(
    series: RelativeBenchmarkSeries,
    *,
    include_benchmark: bool | None,
    analysis_options: DrawdownAnalysisOptions,
) -> RelativeBenchmarkResult:
    if series.benchmark_returns.empty:
        return RelativeBenchmarkResult(
            summary=None,
            context=_relative_benchmark_context(
                include_benchmark=include_benchmark,
                benchmark_available=series.benchmark_available,
            ),
        )

    aligned = pd.merge(
        series.portfolio_returns.to_frame("portfolio"),
        series.benchmark_returns.to_frame("benchmark"),
        left_index=True,
        right_index=True,
        how="inner",
    )
    relative_context = _relative_benchmark_context(
        include_benchmark=include_benchmark,
        benchmark_available=series.benchmark_available,
        aligned_observation_count=len(aligned),
    )
    if aligned.empty:
        return RelativeBenchmarkResult(summary=None, context=relative_context)

    active_drawdown = _drawdown_from_returns(aligned["portfolio"] - aligned["benchmark"])
    active_summary, _ = _drawdown_summary(
        active_drawdown,
        alpha=float(analysis_options.cdar_alpha),
        duration_unit=analysis_options.duration_unit,
    )
    return RelativeBenchmarkResult(
        summary=_relative_drawdown_summary(active_summary),
        context=relative_context,
    )


def _relative_benchmark_context(
    *,
    include_benchmark: bool | None,
    benchmark_available: bool,
    aligned_observation_count: int | None = None,
) -> RelativeDrawdownContext:
    requested = include_benchmark is True
    if aligned_observation_count is not None:
        return RelativeDrawdownContext(
            requested=requested,
            applied=aligned_observation_count > 0,
            reason="APPLIED" if aligned_observation_count > 0 else "NO_ALIGNED_OBSERVATIONS",
            aligned_observation_count=aligned_observation_count,
        )
    return RelativeDrawdownContext(
        requested=requested,
        applied=False,
        reason=(
            "NO_ALIGNED_OBSERVATIONS"
            if benchmark_available
            else "NOT_REQUESTED"
            if not requested
            else "BENCHMARK_UNAVAILABLE"
        ),
        aligned_observation_count=0,
    )


def _relative_drawdown_summary(active_summary: DrawdownSummary) -> RelativeDrawdownSummary:
    return RelativeDrawdownSummary(
        max_drawdown=active_summary.max_drawdown,
        max_drawdown_peak_date=active_summary.max_drawdown_peak_date,
        max_drawdown_trough_date=active_summary.max_drawdown_trough_date,
        max_drawdown_recovery_date=active_summary.max_drawdown_recovery_date,
        is_recovered=active_summary.is_recovered,
        days_to_trough=active_summary.days_to_trough,
        days_to_recovery=active_summary.days_to_recovery,
        time_under_water_days=active_summary.time_under_water_days or 0,
    )
