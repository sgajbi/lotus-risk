from __future__ import annotations

from math import sqrt

import numpy as np
import pandas as pd

from app.services.risk.numeric import as_number

RiskMetricDetails = dict[str, str | float | int | bool | None]

RISK_METRICS_REQUIRING_BENCHMARK = {"BETA", "TRACKING_ERROR", "INFORMATION_RATIO"}
BENCHMARK_METRICS = RISK_METRICS_REQUIRING_BENCHMARK


def beta(portfolio: pd.Series, benchmark: pd.Series) -> tuple[float, RiskMetricDetails]:
    covariance = np.cov(portfolio, benchmark, ddof=1)
    denominator = covariance[1, 1]
    if np.isclose(denominator, 0.0):
        raise ValueError("Benchmark variance is zero")
    covariance_pb = as_number(covariance[0, 1])
    benchmark_variance = as_number(denominator)
    return (
        as_number(covariance_pb / benchmark_variance),
        {
            "aligned_observation_count": int(portfolio.count()),
            "portfolio_mean_return": as_number(portfolio.mean() / 100),
            "benchmark_mean_return": as_number(benchmark.mean() / 100),
            "covariance": covariance_pb,
            "benchmark_variance": benchmark_variance,
        },
    )


def tracking_error(
    portfolio: pd.Series, benchmark: pd.Series, annual_factor: int
) -> tuple[float, RiskMetricDetails]:
    active = portfolio - benchmark
    active_std = as_number(active.std(ddof=1))
    annualized_tracking_error = as_number(active_std * sqrt(annual_factor))
    return (
        annualized_tracking_error,
        {
            "aligned_observation_count": int(active.count()),
            "annualization_factor": annual_factor,
            "portfolio_mean_return": as_number(portfolio.mean() / 100),
            "benchmark_mean_return": as_number(benchmark.mean() / 100),
            "active_mean_return": as_number(active.mean() / 100),
            "active_volatility": active_std / 100,
            "annualized_tracking_error": annualized_tracking_error / 100,
        },
    )


def information_ratio(
    portfolio: pd.Series, benchmark: pd.Series, annual_factor: int
) -> tuple[float, RiskMetricDetails]:
    active = portfolio - benchmark
    tracking_err = active.std(ddof=1)
    if np.isclose(tracking_err, 0.0):
        raise ValueError("Tracking error is zero")
    active_mean = as_number(active.mean() / 100)
    tracking_error_value = as_number(tracking_err / 100)
    annualized_active_return = as_number(active_mean * annual_factor)
    annualized_tracking_error = as_number(tracking_error_value * sqrt(annual_factor))
    return (
        as_number((active.mean() / tracking_err) * sqrt(annual_factor)),
        {
            "aligned_observation_count": int(active.count()),
            "annualization_factor": annual_factor,
            "portfolio_mean_return": as_number(portfolio.mean() / 100),
            "benchmark_mean_return": as_number(benchmark.mean() / 100),
            "active_mean_return": active_mean,
            "tracking_error": tracking_error_value,
            "annualized_active_return": annualized_active_return,
            "annualized_tracking_error": annualized_tracking_error,
        },
    )


def calculate_benchmark_metric(
    metric_name: str, portfolio: pd.Series, benchmark: pd.Series, annual_factor: int
) -> tuple[float, RiskMetricDetails]:
    if metric_name == "BETA":
        return beta(portfolio, benchmark)
    if metric_name == "TRACKING_ERROR":
        return tracking_error(portfolio, benchmark, annual_factor)
    if metric_name == "INFORMATION_RATIO":
        return information_ratio(portfolio, benchmark, annual_factor)
    raise ValueError(f"Unsupported benchmark metric: {metric_name}")


__all__ = [
    "BENCHMARK_METRICS",
    "RISK_METRICS_REQUIRING_BENCHMARK",
    "RiskMetricDetails",
    "beta",
    "calculate_benchmark_metric",
    "information_ratio",
    "tracking_error",
]
