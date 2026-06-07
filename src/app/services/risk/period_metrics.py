from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from app.contracts.risk import RiskStatelessCalculationInput, RiskValue
from app.services.risk import helpers as risk_helpers
from app.services.risk.metric_timing import MetricDurationObserver
from app.services.risk.metric_calculators import (
    align_and_resample_benchmark,
    calculate_drawdown,
    calculate_sharpe,
    calculate_sortino,
    calculate_var,
    calculate_volatility,
    metric_error,
    prepare_benchmark_context,
    resolve_aligned_benchmark_series,
    resolve_benchmark_metric_value,
)


BenchmarkContextPayload = dict[str, str | bool | int | list[str]]


@dataclass(frozen=True)
class _PeriodBenchmarkMetrics:
    metric_map: dict[str, RiskValue]
    benchmark_context: BenchmarkContextPayload
    aligned_count: int
    benchmark_observation_count: int


@dataclass(frozen=True)
class _PeriodNonBenchmarkMetrics:
    metric_series: pd.Series
    metric_map: dict[str, RiskValue]


@dataclass(frozen=True)
class _BenchmarkPeriodMetrics:
    metric_map: dict[str, RiskValue]
    aligned_count: int
    benchmark_observation_count: int


@dataclass(frozen=True)
class PeriodMetricCalculationRequest:
    request: RiskStatelessCalculationInput
    start: pd.Timestamp
    end: pd.Timestamp
    annual_factor: int
    periodic_rf: float
    periodic_mar: float
    period_returns: pd.Series
    benchmark_df: pd.DataFrame
    benchmark_metrics: Sequence[str]
    observe_metric_duration: MetricDurationObserver


def _build_non_benchmark_calculators(
    *,
    period_returns: pd.Series,
    drawdown_series: pd.Series,
    request: RiskStatelessCalculationInput,
    annual_factor: int,
    periodic_rf: float,
    periodic_mar: float,
) -> dict[str, Callable[[], RiskValue]]:
    return {
        "VOLATILITY": lambda: calculate_volatility(
            metric_series=period_returns,
            annual_factor=annual_factor,
        ),
        "DRAWDOWN": lambda: calculate_drawdown(
            drawdown_series=drawdown_series,
        ),
        "SHARPE": lambda: calculate_sharpe(
            metric_series=period_returns,
            periodic_rf=periodic_rf,
            annual_factor=annual_factor,
        ),
        "SORTINO": lambda: calculate_sortino(
            metric_series=period_returns,
            periodic_mar=periodic_mar,
            annual_factor=annual_factor,
            mar_annual_rate=request.options.mar_annual_rate,
        ),
        "VAR": lambda: calculate_var(
            metric_series=period_returns,
            method=request.options.var.method,
            confidence=request.options.var.confidence,
            horizon_days=request.options.var.horizon_days,
            include_expected_shortfall=request.options.var.include_expected_shortfall,
        ),
    }


def _calculate_requested_non_benchmark_metrics(
    *,
    request: RiskStatelessCalculationInput,
    non_benchmark_calculators: dict[str, Callable[[], RiskValue]],
    observe_metric_duration: MetricDurationObserver,
) -> dict[str, RiskValue]:
    metric_map: dict[str, RiskValue] = {}
    for metric_name, calculator in non_benchmark_calculators.items():
        if metric_name not in request.metrics:
            continue
        with observe_metric_duration(metric_name):
            try:
                metric_map[metric_name] = calculator()
            except ValueError as exc:
                metric_map[metric_name] = metric_error(str(exc))
    return metric_map


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
) -> tuple[dict[str, RiskValue], int]:
    aligned = resolve_aligned_benchmark_series(
        metric_series=metric_series,
        benchmark_series=benchmark_period,
    )
    aligned_count = int(len(aligned))
    if aligned_count < 2:
        return (
            _benchmark_metric_errors(
                benchmark_metrics=benchmark_metrics,
                message="Insufficient aligned observations",
            ),
            aligned_count,
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
    return metric_map, aligned_count


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
    benchmark_period = _benchmark_period_series(
        request=request,
        benchmark_df=benchmark_df,
        start=start,
        end=end,
    )
    benchmark_observation_count = len(benchmark_period)
    if benchmark_period.empty:
        return _insufficient_benchmark_period_metrics(
            benchmark_metrics=benchmark_metrics,
            benchmark_observation_count=benchmark_observation_count,
        )

    metric_map, aligned_count = _calculate_aligned_benchmark_metrics(
        metric_series=metric_series,
        benchmark_period=benchmark_period,
        benchmark_metrics=benchmark_metrics,
        annual_factor=annual_factor,
        observe_metric_duration=observe_metric_duration,
    )
    return _BenchmarkPeriodMetrics(
        metric_map=metric_map,
        aligned_count=aligned_count,
        benchmark_observation_count=benchmark_observation_count,
    )


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


def _calculate_benchmark_metrics(
    *,
    request: RiskStatelessCalculationInput,
    metric_series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
    benchmark_df: pd.DataFrame,
    benchmark_metrics: Sequence[str],
    annual_factor: int,
    observe_metric_duration: MetricDurationObserver,
) -> tuple[dict[str, RiskValue], BenchmarkContextPayload, int, int]:
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
    return (
        benchmark_result.metric_map,
        benchmark_context,
        benchmark_result.aligned_count,
        benchmark_result.benchmark_observation_count,
    )


def _period_non_benchmark_metrics(
    *,
    request: RiskStatelessCalculationInput,
    annual_factor: int,
    periodic_rf: float,
    periodic_mar: float,
    period_returns: pd.Series,
    observe_metric_duration: MetricDurationObserver,
) -> _PeriodNonBenchmarkMetrics:
    metric_series = risk_helpers._resample_returns(period_returns, request.options.frequency)
    return _PeriodNonBenchmarkMetrics(
        metric_series=metric_series,
        metric_map=_calculate_requested_non_benchmark_metrics(
            request=request,
            non_benchmark_calculators=_build_non_benchmark_calculators(
                period_returns=metric_series,
                drawdown_series=period_returns,
                request=request,
                annual_factor=annual_factor,
                periodic_rf=periodic_rf,
                periodic_mar=periodic_mar,
            ),
            observe_metric_duration=observe_metric_duration,
        ),
    )


def _period_benchmark_metrics(
    *,
    request: RiskStatelessCalculationInput,
    metric_series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
    benchmark_df: pd.DataFrame,
    benchmark_metrics: Sequence[str],
    annual_factor: int,
    observe_metric_duration: MetricDurationObserver,
) -> _PeriodBenchmarkMetrics | None:
    if not benchmark_metrics:
        return None

    metric_map, benchmark_context, aligned_count, benchmark_observation_count = (
        _calculate_benchmark_metrics(
            request=request,
            metric_series=metric_series,
            start=start,
            end=end,
            benchmark_df=benchmark_df,
            benchmark_metrics=benchmark_metrics,
            annual_factor=annual_factor,
            observe_metric_duration=observe_metric_duration,
        )
    )
    return _PeriodBenchmarkMetrics(
        metric_map=metric_map,
        benchmark_context=benchmark_context,
        aligned_count=aligned_count,
        benchmark_observation_count=benchmark_observation_count,
    )


def _period_metric_result_tuple(
    *,
    non_benchmark_result: _PeriodNonBenchmarkMetrics,
    benchmark_result: _PeriodBenchmarkMetrics | None,
) -> tuple[
    dict[str, RiskValue],
    BenchmarkContextPayload | None,
    int,
    int,
]:
    if benchmark_result is None:
        return non_benchmark_result.metric_map, None, 0, 0

    metric_map = non_benchmark_result.metric_map
    metric_map.update(benchmark_result.metric_map)
    return (
        metric_map,
        benchmark_result.benchmark_context,
        benchmark_result.aligned_count,
        benchmark_result.benchmark_observation_count,
    )


def calculate_period_metrics(
    calculation_request: PeriodMetricCalculationRequest,
) -> tuple[
    dict[str, RiskValue],
    BenchmarkContextPayload | None,
    int,
    int,
]:
    non_benchmark_result = _period_non_benchmark_metrics(
        request=calculation_request.request,
        annual_factor=calculation_request.annual_factor,
        periodic_rf=calculation_request.periodic_rf,
        periodic_mar=calculation_request.periodic_mar,
        period_returns=calculation_request.period_returns,
        observe_metric_duration=calculation_request.observe_metric_duration,
    )
    benchmark_result = _period_benchmark_metrics(
        request=calculation_request.request,
        metric_series=non_benchmark_result.metric_series,
        start=calculation_request.start,
        end=calculation_request.end,
        benchmark_df=calculation_request.benchmark_df,
        benchmark_metrics=calculation_request.benchmark_metrics,
        annual_factor=calculation_request.annual_factor,
        observe_metric_duration=calculation_request.observe_metric_duration,
    )
    return _period_metric_result_tuple(
        non_benchmark_result=non_benchmark_result,
        benchmark_result=benchmark_result,
    )


__all__ = ["BenchmarkContextPayload", "PeriodMetricCalculationRequest", "calculate_period_metrics"]
