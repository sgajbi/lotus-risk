from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

from app.contracts.rolling import (
    RollingMetric,
    ROLLING_BENCHMARK_METRICS,
)
from app.services.rolling_benchmark_metric_series import (
    calculate_rolling_benchmark_metric_values,
)
from app.services.rolling_max_drawdown_series import rolling_max_drawdown_metric

# These explicit aliases are public compatibility re-exports; removing them would silently narrow
# the facade even though the local module does not call them.
from app.services.rolling_metric_outputs import (
    rolling_metric_series_context as rolling_metric_series_context,  # noqa: PLC0414
)
from app.services.rolling_metric_outputs import (
    rolling_metric_series_points as rolling_metric_series_points,  # noqa: PLC0414
)
from app.services.rolling_metric_outputs import (
    rolling_metric_summary as rolling_metric_summary,  # noqa: PLC0414
)

ROLLING_SHARPE_METRIC: RollingMetric = "ROLLING_SHARPE"
ROLLING_MAX_DRAWDOWN_METRIC = "ROLLING_MAX_DRAWDOWN"


@dataclass(frozen=True)
class RollingMetricCalculation:
    values: pd.Series
    quality_flags: list[str]
    aligned_benchmark_series_count: int
    aligned_risk_free_series_count: int


@dataclass(frozen=True)
class _RollingMetricCalculationContext:
    portfolio_decimal: pd.Series
    benchmark_decimal: pd.Series
    risk_free_decimal: pd.Series
    window_length: int
    annualization_basis: int
    min_obs: int


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
    context = _RollingMetricCalculationContext(
        portfolio_decimal=portfolio_decimal,
        benchmark_decimal=benchmark_decimal,
        risk_free_decimal=risk_free_decimal,
        window_length=window_length,
        annualization_basis=annualization_basis,
        min_obs=min_obs,
    )
    if metric_name == "ROLLING_VOLATILITY":
        return _rolling_volatility_calculation(context)
    if metric_name == ROLLING_SHARPE_METRIC:
        return _rolling_sharpe_calculation(context)
    if metric_name in ROLLING_BENCHMARK_METRICS:
        return _rolling_benchmark_calculation(metric_name, context)
    if metric_name == ROLLING_MAX_DRAWDOWN_METRIC:
        return _rolling_max_drawdown_calculation(context)
    raise ValueError(f"Unsupported rolling metric: {metric_name}")


def _rolling_volatility_calculation(
    context: _RollingMetricCalculationContext,
) -> RollingMetricCalculation:
    return _without_dependency_counts(
        _rolling_volatility(
            context.portfolio_decimal,
            window_length=context.window_length,
            annualization_basis=context.annualization_basis,
            min_obs=context.min_obs,
        )
    )


def _rolling_sharpe_calculation(
    context: _RollingMetricCalculationContext,
) -> RollingMetricCalculation:
    metric_values, flags, aligned_count = _rolling_sharpe(
        context.portfolio_decimal,
        context.risk_free_decimal,
        window_length=context.window_length,
        annualization_basis=context.annualization_basis,
        min_obs=context.min_obs,
    )
    return _with_risk_free_count(metric_values, flags, aligned_count)


def _rolling_benchmark_calculation(
    metric_name: str,
    context: _RollingMetricCalculationContext,
) -> RollingMetricCalculation:
    result = calculate_rolling_benchmark_metric_values(
        metric_name,
        portfolio_decimal=context.portfolio_decimal,
        benchmark_decimal=context.benchmark_decimal,
        window_length=context.window_length,
        annualization_basis=context.annualization_basis,
        min_obs=context.min_obs,
    )
    return _with_benchmark_count(
        result.values,
        result.quality_flags,
        result.aligned_benchmark_series_count,
    )


def _rolling_max_drawdown_calculation(
    context: _RollingMetricCalculationContext,
) -> RollingMetricCalculation:
    return _without_dependency_counts(
        rolling_max_drawdown_metric(
            context.portfolio_decimal,
            window_length=context.window_length,
            min_obs=context.min_obs,
        )
    )


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
