from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import pandas as pd

from app.contracts.rolling import (
    ROLLING_BENCHMARK_METRICS,
    RollingBenchmarkContext,
    RollingInputMode,
    RollingMetadata,
    RollingOptions,
    RollingPeriodResult,
    RollingRequestDependencyContext,
    RollingResponse,
    RollingRiskFreeContext,
    RollingStatelessInput,
)
from app.contracts.risk import RiskCalculationSupportability
from app.services.audit_lineage import fingerprint_model
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_period_results,
)
from app.services.rolling_dependency_context import benchmark_context, risk_free_context
from app.services.rolling_engine_models import (
    RollingInputFrames,
    RollingPeriodSeries,
    RollingPeriodWindowAggregate,
)
from app.services.rolling_metric_series import ROLLING_SHARPE_METRIC
from app.services.rolling_period_series import (
    build_rolling_input_frames,
    rolling_period_series,
)
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


def _request_dependency_context(
    requested_metrics: Sequence[str], dependency_metrics: set[str]
) -> RollingRequestDependencyContext:
    requested = [metric for metric in requested_metrics if metric in dependency_metrics]
    return RollingRequestDependencyContext(
        requested=bool(requested),
        requested_metrics=requested,
    )


def _response_metadata(
    request: RollingStatelessInput,
    *,
    requested_metrics: Sequence[str],
    calculation_supportability: RiskCalculationSupportability,
) -> RollingMetadata:
    options = request.rolling_options
    return RollingMetadata(
        request_fingerprint=fingerprint_model(request),
        annualization_basis=options.annualization_basis,
        requested_metrics=[str(metric) for metric in requested_metrics],
        window_lengths_requested=list(options.window_lengths),
        window_count_requested=len(options.window_lengths),
        alignment_policy=options.alignment_policy,
        min_observations_policy=options.min_observations_policy,
        include_time_series=options.include_time_series,
        benchmark_context=_request_dependency_context(
            requested_metrics,
            ROLLING_BENCHMARK_METRICS,
        ),
        risk_free_context=_request_dependency_context(
            requested_metrics,
            {ROLLING_SHARPE_METRIC},
        ),
        calculation_supportability=calculation_supportability,
    )


def _empty_response(
    request: RollingStatelessInput,
    *,
    input_mode: RollingInputMode,
) -> RollingResponse:
    calculation_supportability = supportability_from_period_results(
        returns=request.returns,
        as_of_date=request.scope.as_of_date,
        results={},
    )
    record_operation_supportability(
        operation="risk/rolling-metrics",
        supportability=calculation_supportability,
    )
    requested_metrics = [str(metric) for metric in request.rolling_options.metrics]
    return RollingResponse(
        input_mode=input_mode,
        scope=request.scope,
        results={},
        metadata=_response_metadata(
            request,
            requested_metrics=requested_metrics,
            calculation_supportability=calculation_supportability,
        ),
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


def _rolling_period_results(
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


def calculate_rolling_metrics(
    request: RollingStatelessInput,
    *,
    input_mode: RollingInputMode,
) -> RollingResponse:
    frames = build_rolling_input_frames(request)
    if frames.portfolio.empty:
        return _empty_response(request, input_mode=input_mode)

    options = request.rolling_options
    requested_metrics = [str(metric) for metric in options.metrics]
    results = _rolling_period_results(
        request,
        frames=frames,
        options=options,
        requested_metrics=requested_metrics,
    )

    calculation_supportability = supportability_from_period_results(
        returns=request.returns,
        as_of_date=request.scope.as_of_date,
        results=results,
    )
    record_operation_supportability(
        operation="risk/rolling-metrics",
        supportability=calculation_supportability,
    )
    return RollingResponse(
        input_mode=input_mode,
        scope=request.scope,
        results=results,
        metadata=_response_metadata(
            request,
            requested_metrics=requested_metrics,
            calculation_supportability=calculation_supportability,
        ),
    )
