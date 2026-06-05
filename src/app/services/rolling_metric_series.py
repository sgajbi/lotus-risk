from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt
from typing import cast

import numpy as np
import pandas as pd

from app.contracts.rolling import (
    ROLLING_BENCHMARK_METRICS,
    RollingMetricSeriesContext,
    RollingMetricSeriesPoint,
    RollingMetricSummary,
)


ROLLING_SHARPE_METRIC = "ROLLING_SHARPE"
ROLLING_MAX_DRAWDOWN_METRIC = "ROLLING_MAX_DRAWDOWN"


@dataclass(frozen=True)
class RollingMetricCalculation:
    values: pd.Series
    quality_flags: list[str]
    aligned_benchmark_series_count: int
    aligned_risk_free_series_count: int


def min_observations(window_length: int, policy: str) -> int:
    if policy == "ALLOW_PARTIAL":
        return 2
    return window_length


def rolling_metric_summary(values: pd.Series, *, min_obs: int) -> RollingMetricSummary:
    clean = values.dropna()
    total_point_count = int(values.shape[0])
    warmup_point_count = min(total_point_count, max(min_obs - 1, 0))
    non_computed_point_count = total_point_count - int(clean.count())
    post_warmup_gap_point_count = max(non_computed_point_count - warmup_point_count, 0)
    if clean.empty:
        return RollingMetricSummary(
            total_point_count=total_point_count,
            computed_point_count=0,
            coverage_ratio=0.0,
            min_observations_required=min_obs,
            warmup_point_count=warmup_point_count,
            non_computed_point_count=non_computed_point_count,
            post_warmup_gap_point_count=post_warmup_gap_point_count,
            latest_observation_date=None,
            latest=None,
            average=None,
            minimum=None,
            maximum=None,
            p05=None,
            p50=None,
            p95=None,
        )
    return RollingMetricSummary(
        total_point_count=total_point_count,
        computed_point_count=int(clean.count()),
        coverage_ratio=float(clean.count() / total_point_count) if total_point_count else 0.0,
        min_observations_required=min_obs,
        warmup_point_count=warmup_point_count,
        non_computed_point_count=non_computed_point_count,
        post_warmup_gap_point_count=post_warmup_gap_point_count,
        latest_observation_date=cast(pd.Timestamp, clean.index[-1]).date(),
        latest=float(clean.iloc[-1]),
        average=float(clean.mean()),
        minimum=float(clean.min()),
        maximum=float(clean.max()),
        p05=float(clean.quantile(0.05)),
        p50=float(clean.quantile(0.50)),
        p95=float(clean.quantile(0.95)),
    )


def rolling_metric_series_points(
    metric_series_map: dict[str, pd.Series],
) -> list[RollingMetricSeriesPoint]:
    if not metric_series_map:
        return []

    points_by_date: dict[date, dict[str, float | None]] = {}
    for metric_name, series in metric_series_map.items():
        for index, observation in series.items():
            timestamp = cast(pd.Timestamp, index)
            day = timestamp.date()
            if day not in points_by_date:
                points_by_date[day] = {}
            numeric_observation = float(observation) if pd.notna(observation) else None
            points_by_date[day][metric_name] = numeric_observation

    ordered_dates = sorted(points_by_date.keys())
    return [
        RollingMetricSeriesPoint(date=day, metric_values=points_by_date[day])
        for day in ordered_dates
    ]


def rolling_metric_series_context(
    *,
    include_time_series: bool,
    metric_points: list[RollingMetricSeriesPoint] | None,
) -> RollingMetricSeriesContext:
    emitted_point_count = len(metric_points or [])
    if not include_time_series:
        return RollingMetricSeriesContext(
            requested=False,
            included=False,
            emitted_point_count=0,
            reason="OMITTED_BY_REQUEST",
        )
    if emitted_point_count == 0:
        return RollingMetricSeriesContext(
            requested=True,
            included=False,
            emitted_point_count=0,
            reason="NO_METRIC_SERIES",
        )
    return RollingMetricSeriesContext(
        requested=True,
        included=True,
        emitted_point_count=emitted_point_count,
        reason="INCLUDED",
    )


def calculate_rolling_metric_values(
    metric_name: str,
    *,
    portfolio_decimal: pd.Series,
    benchmark_decimal: pd.Series,
    risk_free_decimal: pd.Series,
    window_length: int,
    annualization_basis: int,
    min_obs: int,
) -> RollingMetricCalculation:
    if metric_name == "ROLLING_VOLATILITY":
        return RollingMetricCalculation(
            values=_rolling_volatility(
                portfolio_decimal,
                window_length=window_length,
                annualization_basis=annualization_basis,
                min_obs=min_obs,
            ),
            quality_flags=[],
            aligned_benchmark_series_count=0,
            aligned_risk_free_series_count=0,
        )
    if metric_name == ROLLING_SHARPE_METRIC:
        metric_values, flags, aligned_count = _rolling_sharpe(
            portfolio_decimal,
            risk_free_decimal,
            window_length=window_length,
            annualization_basis=annualization_basis,
            min_obs=min_obs,
        )
        return RollingMetricCalculation(
            values=metric_values,
            quality_flags=flags,
            aligned_benchmark_series_count=0,
            aligned_risk_free_series_count=aligned_count,
        )
    if metric_name in ROLLING_BENCHMARK_METRICS:
        metric_values, flags, aligned_count = _rolling_benchmark_metrics(
            metric_name,
            portfolio_decimal,
            benchmark_decimal,
            window_length=window_length,
            annualization_basis=annualization_basis,
            min_obs=min_obs,
        )
        return RollingMetricCalculation(
            values=metric_values,
            quality_flags=flags,
            aligned_benchmark_series_count=aligned_count,
            aligned_risk_free_series_count=0,
        )
    if metric_name == ROLLING_MAX_DRAWDOWN_METRIC:
        return RollingMetricCalculation(
            values=_rolling_max_drawdown_metric(
                portfolio_decimal,
                window_length=window_length,
                min_obs=min_obs,
            ),
            quality_flags=[],
            aligned_benchmark_series_count=0,
            aligned_risk_free_series_count=0,
        )
    raise ValueError(f"Unsupported rolling metric: {metric_name}")


def _rolling_volatility(
    series_decimal: pd.Series, *, window_length: int, annualization_basis: int, min_obs: int
) -> pd.Series:
    return series_decimal.rolling(window=window_length, min_periods=min_obs).std(ddof=1) * sqrt(
        annualization_basis
    )


def _rolling_sharpe(
    portfolio_decimal: pd.Series,
    risk_free_decimal: pd.Series,
    *,
    window_length: int,
    annualization_basis: int,
    min_obs: int,
) -> tuple[pd.Series, list[str], int]:
    aligned = pd.merge(
        portfolio_decimal.to_frame("portfolio"),
        risk_free_decimal.to_frame("risk_free"),
        left_index=True,
        right_index=True,
        how="inner",
    )
    if aligned.empty:
        return pd.Series(dtype="float64"), ["metric:ROLLING_SHARPE:alignment_empty"], 0

    active = aligned["portfolio"] - aligned["risk_free"]
    roll_mean = active.rolling(window=window_length, min_periods=min_obs).mean()
    roll_std = active.rolling(window=window_length, min_periods=min_obs).std(ddof=1)
    sharpe = (roll_mean / roll_std) * sqrt(annualization_basis)
    sharpe = sharpe.replace([np.inf, -np.inf], np.nan)
    flags: list[str] = []
    if roll_std.dropna().eq(0).any():
        flags.append("metric:ROLLING_SHARPE:zero_volatility_window")
    return sharpe, flags, int(aligned.shape[0])


def _rolling_benchmark_metrics(
    metric_name: str,
    portfolio_decimal: pd.Series,
    benchmark_decimal: pd.Series,
    *,
    window_length: int,
    annualization_basis: int,
    min_obs: int,
) -> tuple[pd.Series, list[str], int]:
    aligned = pd.merge(
        portfolio_decimal.to_frame("portfolio"),
        benchmark_decimal.to_frame("benchmark"),
        left_index=True,
        right_index=True,
        how="inner",
    )
    if aligned.empty:
        return pd.Series(dtype="float64"), [f"metric:{metric_name}:alignment_empty"], 0

    portfolio = aligned["portfolio"]
    benchmark = aligned["benchmark"]

    if metric_name == "ROLLING_TRACKING_ERROR":
        active = portfolio - benchmark
        result = active.rolling(window=window_length, min_periods=min_obs).std(ddof=1) * sqrt(
            annualization_basis
        )
        return result, [], int(aligned.shape[0])

    if metric_name == "ROLLING_INFORMATION_RATIO":
        active = portfolio - benchmark
        roll_mean = active.rolling(window=window_length, min_periods=min_obs).mean()
        roll_std = active.rolling(window=window_length, min_periods=min_obs).std(ddof=1)
        result = (roll_mean / roll_std) * sqrt(annualization_basis)
        result = result.replace([np.inf, -np.inf], np.nan)
        flags: list[str] = []
        if roll_std.dropna().eq(0).any():
            flags.append("metric:ROLLING_INFORMATION_RATIO:zero_tracking_error_window")
        return result, flags, int(aligned.shape[0])

    if metric_name == "ROLLING_BETA":
        roll_cov = portfolio.rolling(window=window_length, min_periods=min_obs).cov(benchmark)
        roll_var = benchmark.rolling(window=window_length, min_periods=min_obs).var(ddof=1)
        result = roll_cov / roll_var
        result = result.replace([np.inf, -np.inf], np.nan)
        flags = []
        if roll_var.dropna().eq(0).any():
            flags.append("metric:ROLLING_BETA:benchmark_variance_zero")
        return result, flags, int(aligned.shape[0])

    raise ValueError(f"Unsupported rolling benchmark metric: {metric_name}")


def _rolling_max_drawdown_metric(
    series_decimal: pd.Series, *, window_length: int, min_obs: int
) -> pd.Series:
    return series_decimal.rolling(window=window_length, min_periods=min_obs).apply(
        _rolling_max_drawdown,
        raw=True,
    )


def _rolling_max_drawdown(window_decimal_returns: np.ndarray) -> float:
    wealth = np.cumprod(1.0 + window_decimal_returns)
    running_peak = np.maximum.accumulate(wealth)
    drawdown = wealth / running_peak - 1.0
    return float(np.min(drawdown))
