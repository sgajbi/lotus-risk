from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

from app.contracts.rolling import (
    ROLLING_BENCHMARK_METRICS,
)
from app.services.rolling_metric_outputs import (
    rolling_metric_series_context as rolling_metric_series_context,
    rolling_metric_series_points as rolling_metric_series_points,
    rolling_metric_summary as rolling_metric_summary,
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
        return _without_dependency_counts(
            _rolling_volatility(
                portfolio_decimal,
                window_length=window_length,
                annualization_basis=annualization_basis,
                min_obs=min_obs,
            )
        )
    if metric_name == ROLLING_SHARPE_METRIC:
        metric_values, flags, aligned_count = _rolling_sharpe(
            portfolio_decimal,
            risk_free_decimal,
            window_length=window_length,
            annualization_basis=annualization_basis,
            min_obs=min_obs,
        )
        return _with_risk_free_count(metric_values, flags, aligned_count)
    if metric_name in ROLLING_BENCHMARK_METRICS:
        metric_values, flags, aligned_count = _rolling_benchmark_metrics(
            metric_name,
            portfolio_decimal,
            benchmark_decimal,
            window_length=window_length,
            annualization_basis=annualization_basis,
            min_obs=min_obs,
        )
        return _with_benchmark_count(metric_values, flags, aligned_count)
    if metric_name == ROLLING_MAX_DRAWDOWN_METRIC:
        return _without_dependency_counts(
            _rolling_max_drawdown_metric(
                portfolio_decimal,
                window_length=window_length,
                min_obs=min_obs,
            )
        )
    raise ValueError(f"Unsupported rolling metric: {metric_name}")


def _without_dependency_counts(values: pd.Series) -> RollingMetricCalculation:
    return RollingMetricCalculation(
        values=values,
        quality_flags=[],
        aligned_benchmark_series_count=0,
        aligned_risk_free_series_count=0,
    )


def _with_benchmark_count(
    values: pd.Series,
    quality_flags: list[str],
    aligned_count: int,
) -> RollingMetricCalculation:
    return RollingMetricCalculation(
        values=values,
        quality_flags=quality_flags,
        aligned_benchmark_series_count=aligned_count,
        aligned_risk_free_series_count=0,
    )


def _with_risk_free_count(
    values: pd.Series,
    quality_flags: list[str],
    aligned_count: int,
) -> RollingMetricCalculation:
    return RollingMetricCalculation(
        values=values,
        quality_flags=quality_flags,
        aligned_benchmark_series_count=0,
        aligned_risk_free_series_count=aligned_count,
    )


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


def _rolling_benchmark_metrics(
    metric_name: str,
    portfolio_decimal: pd.Series,
    benchmark_decimal: pd.Series,
    *,
    window_length: int,
    annualization_basis: int,
    min_obs: int,
) -> tuple[pd.Series, list[str], int]:
    aligned = _aligned_portfolio_benchmark(portfolio_decimal, benchmark_decimal)
    if aligned.empty:
        return pd.Series(dtype="float64"), [f"metric:{metric_name}:alignment_empty"], 0

    portfolio = aligned["portfolio"]
    benchmark = aligned["benchmark"]

    if metric_name == "ROLLING_TRACKING_ERROR":
        result, flags = _rolling_tracking_error(
            portfolio,
            benchmark,
            window_length=window_length,
            annualization_basis=annualization_basis,
            min_obs=min_obs,
        )
        return result, flags, int(aligned.shape[0])

    if metric_name == "ROLLING_INFORMATION_RATIO":
        result, flags = _rolling_information_ratio(
            portfolio,
            benchmark,
            window_length=window_length,
            annualization_basis=annualization_basis,
            min_obs=min_obs,
        )
        return result, flags, int(aligned.shape[0])

    if metric_name == "ROLLING_BETA":
        result, flags = _rolling_beta_metric(
            portfolio,
            benchmark,
            window_length=window_length,
            min_obs=min_obs,
        )
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
