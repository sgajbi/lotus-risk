from __future__ import annotations

from collections.abc import Sequence
from typing import Callable

import pandas as pd
from prometheus_client import Histogram

from app.contracts.risk import RiskStatelessCalculationInput, RiskValue
from app.services.risk import helpers as risk_helpers
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
    duration_seconds: Histogram,
) -> dict[str, RiskValue]:
    metric_map: dict[str, RiskValue] = {}
    for metric_name, calculator in non_benchmark_calculators.items():
        if metric_name not in request.metrics:
            continue
        with duration_seconds.labels(metric_name=metric_name).time():
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
    duration_seconds: Histogram,
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
        with duration_seconds.labels(metric_name=metric_name).time():
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


def _calculate_benchmark_metrics(
    *,
    request: RiskStatelessCalculationInput,
    metric_series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
    benchmark_df: pd.DataFrame,
    benchmark_metrics: Sequence[str],
    annual_factor: int,
    duration_seconds: Histogram,
) -> tuple[dict[str, RiskValue], BenchmarkContextPayload, int, int]:
    aligned_count = 0
    benchmark_observation_count = 0
    if benchmark_df.empty:
        metric_map = _benchmark_metric_errors(
            benchmark_metrics=benchmark_metrics,
            message="Benchmark returns required for benchmark-dependent metric",
        )
    else:
        benchmark_period = align_and_resample_benchmark(
            benchmark_df=benchmark_df,
            start=start.date(),
            end=end.date(),
            frequency=request.options.frequency,
            use_log_returns=request.options.use_log_returns,
        )
        benchmark_observation_count = len(benchmark_period)
        if benchmark_period.empty:
            metric_map = _benchmark_metric_errors(
                benchmark_metrics=benchmark_metrics,
                message="Insufficient aligned observations",
            )
        else:
            metric_map, aligned_count = _calculate_aligned_benchmark_metrics(
                metric_series=metric_series,
                benchmark_period=benchmark_period,
                benchmark_metrics=benchmark_metrics,
                annual_factor=annual_factor,
                duration_seconds=duration_seconds,
            )

    benchmark_context = prepare_benchmark_context(
        benchmark_df_empty=benchmark_df.empty,
        aligned_count=aligned_count,
        benchmark_metrics=list(benchmark_metrics),
    )
    return metric_map, benchmark_context, aligned_count, benchmark_observation_count


def calculate_period_metrics(
    request: RiskStatelessCalculationInput,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    annual_factor: int,
    periodic_rf: float,
    periodic_mar: float,
    period_returns: pd.Series,
    benchmark_df: pd.DataFrame,
    benchmark_metrics: Sequence[str],
    duration_seconds: Histogram,
) -> tuple[
    dict[str, RiskValue],
    BenchmarkContextPayload | None,
    int,
    int,
]:
    metric_series = risk_helpers._resample_returns(period_returns, request.options.frequency)
    metric_map = _calculate_requested_non_benchmark_metrics(
        request=request,
        non_benchmark_calculators=_build_non_benchmark_calculators(
            period_returns=metric_series,
            drawdown_series=period_returns,
            request=request,
            annual_factor=annual_factor,
            periodic_rf=periodic_rf,
            periodic_mar=periodic_mar,
        ),
        duration_seconds=duration_seconds,
    )
    if not benchmark_metrics:
        return metric_map, None, 0, 0

    benchmark_map, benchmark_context, aligned_count, benchmark_observation_count = (
        _calculate_benchmark_metrics(
            request=request,
            metric_series=metric_series,
            start=start,
            end=end,
            benchmark_df=benchmark_df,
            benchmark_metrics=benchmark_metrics,
            annual_factor=annual_factor,
            duration_seconds=duration_seconds,
        )
    )
    metric_map.update(benchmark_map)
    return metric_map, benchmark_context, aligned_count, benchmark_observation_count


__all__ = ["BenchmarkContextPayload", "calculate_period_metrics"]
