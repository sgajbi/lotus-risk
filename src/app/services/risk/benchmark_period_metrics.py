from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from app.contracts.risk import RiskStatelessCalculationInput, RiskValue
from app.services.risk.metric_calculators import (
    align_and_resample_benchmark,
    metric_error,
    prepare_benchmark_context,
    resolve_aligned_benchmark_series,
    resolve_benchmark_metric_value,
)
from app.services.risk.metric_timing import MetricDurationObserver

BenchmarkContextPayload = dict[str, str | bool | int | list[str]]


@dataclass(frozen=True)
class BenchmarkPeriodMetricResult:
    metric_map: dict[str, RiskValue]
    benchmark_context: BenchmarkContextPayload
    aligned_count: int
    benchmark_observation_count: int


@dataclass(frozen=True)
class _AlignedBenchmarkMetricResult:
    metric_map: dict[str, RiskValue]
    aligned_count: int


@dataclass(frozen=True)
class _BenchmarkPeriodMetrics:
    metric_map: dict[str, RiskValue]
    aligned_count: int
    benchmark_observation_count: int


def _benchmark_metric_errors(
    *,
    benchmark_metrics: Sequence[str],
    message: str,
) -> dict[str, RiskValue]:
    return {metric_name: metric_error(message) for metric_name in benchmark_metrics}


def _calculate_aligned_benchmark_metrics(
    *,
    metric_series: pd.Series,
    benchmark_period: pd.Series,
    benchmark_metrics: Sequence[str],
    annual_factor: int,
    observe_metric_duration: MetricDurationObserver,
) -> _AlignedBenchmarkMetricResult:
    aligned = resolve_aligned_benchmark_series(
        metric_series=metric_series,
        benchmark_series=benchmark_period,
    )
    aligned_count = len(aligned)
    if aligned_count < 2:
        return _AlignedBenchmarkMetricResult(
            metric_map=_benchmark_metric_errors(
                benchmark_metrics=benchmark_metrics,
                message="Insufficient aligned observations",
            ),
            aligned_count=aligned_count,
        )

    portfolio_series = pd.Series(aligned["portfolio"])
    benchmark_aligned_series = pd.Series(aligned["benchmark"])
    metric_map: dict[str, RiskValue] = {}
    for metric_name in benchmark_metrics:
        with observe_metric_duration(metric_name):
            try:
                metric_map[metric_name] = resolve_benchmark_metric_value(
                    metric_name=metric_name,
                    aligned_portfolio_series=portfolio_series,
                    aligned_benchmark_series=benchmark_aligned_series,
                    annual_factor=annual_factor,
                )
            except ValueError as exc:
                metric_map[metric_name] = metric_error(str(exc))
    return _AlignedBenchmarkMetricResult(metric_map=metric_map, aligned_count=aligned_count)


def _benchmark_period_series(
    *,
    request: RiskStatelessCalculationInput,
    benchmark_df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    return align_and_resample_benchmark(
        benchmark_df=benchmark_df,
        start=start.date(),
        end=end.date(),
        frequency=request.options.frequency,
        use_log_returns=request.options.use_log_returns,
    )


def _insufficient_benchmark_period_metrics(
    *,
    benchmark_metrics: Sequence[str],
    benchmark_observation_count: int,
    message: str = "Insufficient aligned observations",
) -> _BenchmarkPeriodMetrics:
    return _BenchmarkPeriodMetrics(
        metric_map=_benchmark_metric_errors(
            benchmark_metrics=benchmark_metrics,
            message=message,
        ),
        aligned_count=0,
        benchmark_observation_count=benchmark_observation_count,
    )


def _empty_benchmark_period_metrics(
    benchmark_metrics: Sequence[str],
) -> _BenchmarkPeriodMetrics:
    return _insufficient_benchmark_period_metrics(
        benchmark_metrics=benchmark_metrics,
        benchmark_observation_count=0,
        message="Benchmark returns required for benchmark-dependent metric",
    )


def _benchmark_period_metrics(
    *,
    request: RiskStatelessCalculationInput,
    metric_series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
    benchmark_df: pd.DataFrame,
    benchmark_metrics: Sequence[str],
    annual_factor: int,
    observe_metric_duration: MetricDurationObserver,
) -> _BenchmarkPeriodMetrics:
    try:
        benchmark_period = _benchmark_period_series(
            request=request,
            benchmark_df=benchmark_df,
            start=start,
            end=end,
        )
    except ValueError as exc:
        return _insufficient_benchmark_period_metrics(
            benchmark_metrics=benchmark_metrics,
            benchmark_observation_count=0,
            message=str(exc),
        )
    benchmark_observation_count = len(benchmark_period)
    if benchmark_period.empty:
        return _insufficient_benchmark_period_metrics(
            benchmark_metrics=benchmark_metrics,
            benchmark_observation_count=benchmark_observation_count,
        )

    aligned_result = _calculate_aligned_benchmark_metrics(
        metric_series=metric_series,
        benchmark_period=benchmark_period,
        benchmark_metrics=benchmark_metrics,
        annual_factor=annual_factor,
        observe_metric_duration=observe_metric_duration,
    )
    return _BenchmarkPeriodMetrics(
        metric_map=aligned_result.metric_map,
        aligned_count=aligned_result.aligned_count,
        benchmark_observation_count=benchmark_observation_count,
    )


def calculate_benchmark_period_metrics(
    *,
    request: RiskStatelessCalculationInput,
    metric_series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
    benchmark_df: pd.DataFrame,
    benchmark_metrics: Sequence[str],
    annual_factor: int,
    observe_metric_duration: MetricDurationObserver,
) -> BenchmarkPeriodMetricResult:
    if benchmark_df.empty:
        benchmark_result = _empty_benchmark_period_metrics(benchmark_metrics)
    else:
        benchmark_result = _benchmark_period_metrics(
            request=request,
            metric_series=metric_series,
            start=start,
            end=end,
            benchmark_df=benchmark_df,
            benchmark_metrics=benchmark_metrics,
            annual_factor=annual_factor,
            observe_metric_duration=observe_metric_duration,
        )

    benchmark_context = prepare_benchmark_context(
        benchmark_df_empty=benchmark_df.empty,
        aligned_count=benchmark_result.aligned_count,
        benchmark_metrics=list(benchmark_metrics),
    )
    return BenchmarkPeriodMetricResult(
        metric_map=benchmark_result.metric_map,
        benchmark_context=benchmark_context,
        aligned_count=benchmark_result.aligned_count,
        benchmark_observation_count=benchmark_result.benchmark_observation_count,
    )


__all__ = [
    "BenchmarkContextPayload",
    "BenchmarkPeriodMetricResult",
    "calculate_benchmark_period_metrics",
]
