from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import pandas as pd

from app.contracts.rolling import (
    RollingBenchmarkContext,
    RollingOptions,
    RollingPeriodResult,
    RollingRiskFreeContext,
    RollingStatelessInput,
)
from app.services.rolling_dependency_context import benchmark_context, risk_free_context
from app.services.rolling_engine_models import (
    RollingInputFrames,
    RollingPeriodSeries,
    RollingPeriodWindowAggregate,
)
from app.services.rolling_period_series import rolling_period_series
from app.services.rolling_window_calculation import rolling_period_window_aggregate


@dataclass(frozen=True)
class _RollingPeriodDependencyCounts:
    benchmark_series_count: int
    aligned_benchmark_series_count: int
    risk_free_series_count: int
    aligned_risk_free_series_count: int


@dataclass(frozen=True)
class _RollingPeriodDependencyContexts:
    benchmark: RollingBenchmarkContext
    risk_free: RollingRiskFreeContext


def rolling_period_results(
    request: RollingStatelessInput,
    *,
    frames: RollingInputFrames,
    options: RollingOptions,
    requested_metrics: Sequence[str],
) -> dict[str, RollingPeriodResult]:
    open_date = cast(pd.Timestamp, frames.portfolio.index.min()).date()
    results: dict[str, RollingPeriodResult] = {}
    for period in request.periods:
        period_series = rolling_period_series(
            frames=frames,
            request=request,
            period=period,
            open_date=open_date,
        )
        results[period_series.name] = _calculate_period_result(
            period_series,
            options=options,
            requested_metrics=requested_metrics,
        )
    return results


def _calculate_period_result(
    period_series: RollingPeriodSeries,
    *,
    options: RollingOptions,
    requested_metrics: Sequence[str],
) -> RollingPeriodResult:
    if len(period_series.portfolio_pp) < 2:
        return _insufficient_period_result(
            period_series,
            options=options,
            requested_metrics=requested_metrics,
        )

    aggregate = rolling_period_window_aggregate(
        period_series,
        options=options,
        requested_metrics=requested_metrics,
    )
    return _calculated_period_result(
        period_series,
        aggregate=aggregate,
        options=options,
        requested_metrics=requested_metrics,
    )


def _insufficient_period_result(
    period_series: RollingPeriodSeries,
    *,
    options: RollingOptions,
    requested_metrics: Sequence[str],
) -> RollingPeriodResult:
    return RollingPeriodResult(
        start_date=period_series.start,
        end_date=period_series.end,
        series_count=len(period_series.portfolio_pp),
        benchmark_series_count=0,
        aligned_benchmark_series_count=0,
        risk_free_series_count=0,
        aligned_risk_free_series_count=0,
        window_lengths_requested=list(options.window_lengths),
        window_count_requested=len(options.window_lengths),
        window_lengths_emitted=[],
        window_count_emitted=0,
        benchmark_context=benchmark_context(
            requested_metrics,
            benchmark_series_count=0,
            aligned_benchmark_series_count=0,
        ),
        risk_free_context=risk_free_context(
            requested_metrics,
            risk_free_series_count=0,
            aligned_risk_free_series_count=0,
        ),
        window_results=[],
        quality_flags=[],
        error="Insufficient data",
    )


def _calculated_period_result(
    period_series: RollingPeriodSeries,
    *,
    aggregate: RollingPeriodWindowAggregate,
    options: RollingOptions,
    requested_metrics: Sequence[str],
) -> RollingPeriodResult:
    dependency_counts = _rolling_period_dependency_counts(
        period_series=period_series,
        aligned_benchmark_series_count=aggregate.aligned_benchmark_series_count,
        aligned_risk_free_series_count=aggregate.aligned_risk_free_series_count,
    )
    dependency_contexts = _rolling_period_dependency_contexts(
        requested_metrics=requested_metrics,
        dependency_counts=dependency_counts,
    )

    return RollingPeriodResult(
        start_date=period_series.start,
        end_date=period_series.end,
        series_count=len(period_series.portfolio_decimal),
        benchmark_series_count=dependency_counts.benchmark_series_count,
        aligned_benchmark_series_count=dependency_counts.aligned_benchmark_series_count,
        risk_free_series_count=dependency_counts.risk_free_series_count,
        aligned_risk_free_series_count=dependency_counts.aligned_risk_free_series_count,
        window_lengths_requested=list(options.window_lengths),
        window_count_requested=len(options.window_lengths),
        window_lengths_emitted=[result.window_length for result in aggregate.window_results],
        window_count_emitted=len(aggregate.window_results),
        benchmark_context=dependency_contexts.benchmark,
        risk_free_context=dependency_contexts.risk_free,
        window_results=aggregate.window_results,
        quality_flags=sorted(aggregate.quality_flags),
        error=None,
    )


def _rolling_period_dependency_contexts(
    *,
    requested_metrics: Sequence[str],
    dependency_counts: _RollingPeriodDependencyCounts,
) -> _RollingPeriodDependencyContexts:
    return _RollingPeriodDependencyContexts(
        benchmark=benchmark_context(
            requested_metrics,
            benchmark_series_count=dependency_counts.benchmark_series_count,
            aligned_benchmark_series_count=dependency_counts.aligned_benchmark_series_count,
        ),
        risk_free=risk_free_context(
            requested_metrics,
            risk_free_series_count=dependency_counts.risk_free_series_count,
            aligned_risk_free_series_count=dependency_counts.aligned_risk_free_series_count,
        ),
    )


def _rolling_period_dependency_counts(
    *,
    period_series: RollingPeriodSeries,
    aligned_benchmark_series_count: int,
    aligned_risk_free_series_count: int,
) -> _RollingPeriodDependencyCounts:
    return _RollingPeriodDependencyCounts(
        benchmark_series_count=len(period_series.benchmark_decimal),
        aligned_benchmark_series_count=aligned_benchmark_series_count,
        risk_free_series_count=len(period_series.risk_free_decimal),
        aligned_risk_free_series_count=aligned_risk_free_series_count,
    )


__all__ = ["rolling_period_results"]
