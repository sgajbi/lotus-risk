from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from app.contracts.risk import RiskStatelessCalculationInput, RiskValue
from app.services.risk import helpers as risk_helpers
from app.services.risk.benchmark_period_metrics import (
    BenchmarkContextPayload,
    BenchmarkPeriodMetricResult,
    calculate_benchmark_period_metrics,
)
from app.services.risk.metric_timing import MetricDurationObserver
from app.services.risk.metric_calculators import (
    calculate_drawdown,
    calculate_sharpe,
    calculate_sortino,
    calculate_var,
    calculate_volatility,
    metric_error,
)


@dataclass(frozen=True)
class _PeriodNonBenchmarkMetrics:
    metric_series: pd.Series
    metric_map: dict[str, RiskValue]


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
) -> BenchmarkPeriodMetricResult | None:
    if not benchmark_metrics:
        return None

    return calculate_benchmark_period_metrics(
        request=request,
        metric_series=metric_series,
        start=start,
        end=end,
        benchmark_df=benchmark_df,
        benchmark_metrics=benchmark_metrics,
        annual_factor=annual_factor,
        observe_metric_duration=observe_metric_duration,
    )


def _period_metric_result_tuple(
    *,
    non_benchmark_result: _PeriodNonBenchmarkMetrics,
    benchmark_result: BenchmarkPeriodMetricResult | None,
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
