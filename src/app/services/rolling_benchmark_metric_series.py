from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AlignedBenchmarkSeries:
    portfolio: pd.Series
    benchmark: pd.Series
    observation_count: int


@dataclass(frozen=True)
class RollingBenchmarkMetricCalculation:
    values: pd.Series
    quality_flags: list[str]
    aligned_benchmark_series_count: int


def _aligned_portfolio_benchmark(
    portfolio_decimal: pd.Series,
    benchmark_decimal: pd.Series,
) -> pd.DataFrame:
    return pd.merge(
        portfolio_decimal.to_frame("portfolio"),
        benchmark_decimal.to_frame("benchmark"),
        left_index=True,
        right_index=True,
        how="inner",
    )


def _aligned_benchmark_series(aligned: pd.DataFrame) -> AlignedBenchmarkSeries:
    return AlignedBenchmarkSeries(
        portfolio=aligned["portfolio"],
        benchmark=aligned["benchmark"],
        observation_count=int(aligned.shape[0]),
    )


def _active_rolling_returns(
    portfolio: pd.Series,
    benchmark: pd.Series,
) -> pd.Series:
    return portfolio - benchmark


def _rolling_tracking_error(
    portfolio: pd.Series,
    benchmark: pd.Series,
    *,
    window_length: int,
    annualization_basis: int,
    min_obs: int,
) -> tuple[pd.Series, list[str]]:
    active = _active_rolling_returns(portfolio, benchmark)
    result = active.rolling(window=window_length, min_periods=min_obs).std(ddof=1) * sqrt(
        annualization_basis
    )
    return result, []


def _rolling_information_ratio(
    portfolio: pd.Series,
    benchmark: pd.Series,
    *,
    window_length: int,
    annualization_basis: int,
    min_obs: int,
) -> tuple[pd.Series, list[str]]:
    active = _active_rolling_returns(portfolio, benchmark)
    roll_mean = active.rolling(window=window_length, min_periods=min_obs).mean()
    roll_std = active.rolling(window=window_length, min_periods=min_obs).std(ddof=1)
    result = (roll_mean / roll_std) * sqrt(annualization_basis)
    result = result.replace([np.inf, -np.inf], np.nan)
    flags: list[str] = []
    if roll_std.dropna().eq(0).any():
        flags.append("metric:ROLLING_INFORMATION_RATIO:zero_tracking_error_window")
    return result, flags


def _rolling_beta_metric(
    portfolio: pd.Series,
    benchmark: pd.Series,
    *,
    window_length: int,
    min_obs: int,
) -> tuple[pd.Series, list[str]]:
    roll_cov = portfolio.rolling(window=window_length, min_periods=min_obs).cov(benchmark)
    roll_var = benchmark.rolling(window=window_length, min_periods=min_obs).var(ddof=1)
    result = roll_cov / roll_var
    result = result.replace([np.inf, -np.inf], np.nan)
    flags: list[str] = []
    if roll_var.dropna().eq(0).any():
        flags.append("metric:ROLLING_BETA:benchmark_variance_zero")
    return result, flags


def _calculate_aligned_rolling_benchmark_metric(
    metric_name: str,
    aligned_series: AlignedBenchmarkSeries,
    *,
    window_length: int,
    annualization_basis: int,
    min_obs: int,
) -> tuple[pd.Series, list[str]]:
    if metric_name == "ROLLING_TRACKING_ERROR":
        return _rolling_tracking_error(
            aligned_series.portfolio,
            aligned_series.benchmark,
            window_length=window_length,
            annualization_basis=annualization_basis,
            min_obs=min_obs,
        )

    if metric_name == "ROLLING_INFORMATION_RATIO":
        return _rolling_information_ratio(
            aligned_series.portfolio,
            aligned_series.benchmark,
            window_length=window_length,
            annualization_basis=annualization_basis,
            min_obs=min_obs,
        )

    if metric_name == "ROLLING_BETA":
        return _rolling_beta_metric(
            aligned_series.portfolio,
            aligned_series.benchmark,
            window_length=window_length,
            min_obs=min_obs,
        )

    raise ValueError(f"Unsupported rolling benchmark metric: {metric_name}")


def calculate_rolling_benchmark_metric_values(
    metric_name: str,
    *,
    portfolio_decimal: pd.Series,
    benchmark_decimal: pd.Series,
    window_length: int,
    annualization_basis: int,
    min_obs: int,
) -> RollingBenchmarkMetricCalculation:
    aligned = _aligned_portfolio_benchmark(portfolio_decimal, benchmark_decimal)
    if aligned.empty:
        return RollingBenchmarkMetricCalculation(
            values=pd.Series(dtype="float64"),
            quality_flags=[f"metric:{metric_name}:alignment_empty"],
            aligned_benchmark_series_count=0,
        )

    aligned_series = _aligned_benchmark_series(aligned)
    result, flags = _calculate_aligned_rolling_benchmark_metric(
        metric_name,
        aligned_series,
        window_length=window_length,
        annualization_basis=annualization_basis,
        min_obs=min_obs,
    )
    return RollingBenchmarkMetricCalculation(
        values=result,
        quality_flags=flags,
        aligned_benchmark_series_count=aligned_series.observation_count,
    )


__all__ = [
    "RollingBenchmarkMetricCalculation",
    "calculate_rolling_benchmark_metric_values",
]
