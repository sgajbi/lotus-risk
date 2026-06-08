from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from app.contracts.risk import RiskPeriodResult, RiskStatelessCalculationInput, RiskValue
from app.services.risk.period_metrics import (
    BenchmarkContextPayload,
    PeriodMetricCalculationRequest,
    calculate_period_metrics,
)
from app.services.risk.metric_timing import MetricDurationObserver
from app.services.risk.period_windows import RiskPeriodWindow, risk_period_window


@dataclass(frozen=True)
class _PeriodMetricCalculation:
    metric_map: dict[str, RiskValue]
    benchmark_context: BenchmarkContextPayload | None
    aligned_count: int
    benchmark_observation_count: int


def build_period_results(
    request: RiskStatelessCalculationInput,
    *,
    annual_factor: int,
    periodic_rf: float,
    periodic_mar: float,
    returns_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    benchmark_metrics: set[str],
    observe_metric_duration: MetricDurationObserver,
) -> dict[str, RiskPeriodResult]:
    benchmark_metrics_for_request = [
        metric for metric in request.metrics if metric in benchmark_metrics
    ]

    results: dict[str, RiskPeriodResult] = {}
    for period_index, _period in enumerate(request.periods):
        period_name, period_result = _build_single_period_result(
            request=request,
            period_index=period_index,
            annual_factor=annual_factor,
            periodic_rf=periodic_rf,
            periodic_mar=periodic_mar,
            returns_df=returns_df,
            benchmark_df=benchmark_df,
            benchmark_metrics=benchmark_metrics_for_request,
            observe_metric_duration=observe_metric_duration,
        )
        results[period_name] = period_result

    return results


def _build_single_period_result(
    request: RiskStatelessCalculationInput,
    *,
    period_index: int,
    annual_factor: int,
    periodic_rf: float,
    periodic_mar: float,
    returns_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    benchmark_metrics: Sequence[str],
    observe_metric_duration: MetricDurationObserver,
) -> tuple[str, RiskPeriodResult]:
    period_window = risk_period_window(
        request=request,
        period_index=period_index,
        returns_df=returns_df,
    )
    calculation = _period_metric_calculation(
        request,
        period_window=period_window,
        annual_factor=annual_factor,
        periodic_rf=periodic_rf,
        periodic_mar=periodic_mar,
        benchmark_df=benchmark_df,
        benchmark_metrics=benchmark_metrics,
        observe_metric_duration=observe_metric_duration,
    )

    return period_window.name, _period_result(
        period_window=period_window,
        metric_map=calculation.metric_map,
        benchmark_context=calculation.benchmark_context,
        aligned_count=calculation.aligned_count,
        benchmark_observation_count=calculation.benchmark_observation_count,
        benchmark_df=benchmark_df,
    )


def _period_metric_calculation(
    request: RiskStatelessCalculationInput,
    *,
    period_window: RiskPeriodWindow,
    annual_factor: int,
    periodic_rf: float,
    periodic_mar: float,
    benchmark_df: pd.DataFrame,
    benchmark_metrics: Sequence[str],
    observe_metric_duration: MetricDurationObserver,
) -> _PeriodMetricCalculation:
    return _period_metric_calculation_result(
        calculate_period_metrics(
            PeriodMetricCalculationRequest(
                request=request,
                start=period_window.start,
                end=period_window.end,
                annual_factor=annual_factor,
                periodic_rf=periodic_rf,
                periodic_mar=periodic_mar,
                period_returns=period_window.returns,
                benchmark_df=benchmark_df,
                benchmark_metrics=benchmark_metrics,
                observe_metric_duration=observe_metric_duration,
            )
        )
    )


def _period_metric_calculation_result(
    result: tuple[dict[str, RiskValue], BenchmarkContextPayload | None, int, int],
) -> _PeriodMetricCalculation:
    metric_map, benchmark_context, aligned_count, benchmark_observation_count = result
    return _PeriodMetricCalculation(
        metric_map=metric_map,
        benchmark_context=benchmark_context,
        aligned_count=aligned_count,
        benchmark_observation_count=benchmark_observation_count,
    )


def _period_result(
    *,
    period_window: RiskPeriodWindow,
    metric_map: dict[str, RiskValue],
    benchmark_context: BenchmarkContextPayload | None,
    aligned_count: int,
    benchmark_observation_count: int,
    benchmark_df: pd.DataFrame,
) -> RiskPeriodResult:
    return RiskPeriodResult(
        start_date=period_window.start.date(),
        end_date=period_window.end.date(),
        portfolio_observation_count=len(period_window.returns),
        benchmark_observation_count=(
            benchmark_observation_count
            if (not benchmark_df.empty and benchmark_context is not None)
            else 0
        ),
        aligned_benchmark_observation_count=(aligned_count if benchmark_context else 0),
        benchmark_context=benchmark_context,
        metrics=metric_map,
    )


__all__ = ["build_period_results"]
