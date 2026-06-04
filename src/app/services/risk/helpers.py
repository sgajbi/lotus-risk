from __future__ import annotations

from datetime import date, timedelta
from math import sqrt
from statistics import NormalDist
from typing import SupportsFloat, cast

import numpy as np
import pandas as pd

RiskMetricDetails = dict[str, str | float | int | bool | None]

RISK_METRICS_REQUIRING_BENCHMARK = {"BETA", "TRACKING_ERROR", "INFORMATION_RATIO"}
RISK_METRICS_REQUIRING_RISK_FREE = {"SHARPE"}


def _as_number(number: SupportsFloat) -> float:
    return float(number)


def _resolve_period(
    period_type: str,
    as_of: date,
    open_date: date,
    *,
    year: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[date, date]:
    if period_type == "EXPLICIT":
        if from_date is None or to_date is None:
            raise ValueError("EXPLICIT period requires from/to dates")
        start, end = from_date, to_date
    elif period_type == "YEAR":
        if year is None:
            raise ValueError("YEAR period requires year")
        start, end = date(year, 1, 1), date(year, 12, 31)
    elif period_type == "YTD":
        start, end = date(as_of.year, 1, 1), as_of
    elif period_type == "QTD":
        quarter_start_month = (as_of.month - 1) // 3 * 3 + 1
        start, end = date(as_of.year, quarter_start_month, 1), as_of
    elif period_type == "MTD":
        start, end = date(as_of.year, as_of.month, 1), as_of
    elif period_type == "1Y":
        start, end = as_of - timedelta(days=365) + timedelta(days=1), as_of
    elif period_type == "3Y":
        start, end = as_of - timedelta(days=365 * 3) + timedelta(days=1), as_of
    elif period_type == "5Y":
        start, end = as_of - timedelta(days=365 * 5) + timedelta(days=1), as_of
    elif period_type == "SI":
        start, end = open_date, as_of
    else:
        raise ValueError(f"Unsupported period type: {period_type}")

    return max(start, open_date), end


def _resample_returns(returns: pd.Series, frequency: str) -> pd.Series:
    if returns.empty:
        return returns
    if frequency == "DAILY":
        return returns
    rule = {"WEEKLY": "W-FRI", "MONTHLY": "ME"}[frequency]
    resampled = returns.resample(rule).apply(lambda x: ((1 + x / 100).prod() - 1) * 100).dropna()
    if isinstance(resampled, pd.DataFrame):
        if resampled.shape[1] != 1:
            raise TypeError(f"Unexpected resample result shape: {resampled.shape}")
        resampled = resampled.iloc[:, 0]
    return resampled


def _to_log_returns(returns: pd.Series) -> pd.Series:
    if returns.empty:
        return returns
    return pd.Series(np.log1p(returns / 100) * 100, index=returns.index, name=returns.name)


def _annual_to_periodic(rate: float, annual_factor: int) -> float:
    return float((1.0 + float(rate)) ** (1.0 / float(annual_factor)) - 1.0)


def _drawdown(returns: pd.Series) -> dict[str, str | float | None]:
    wealth = (1 + returns / 100).cumprod()
    peak = wealth.cummax()
    drawdown = wealth / peak - 1
    if drawdown.empty:
        return {
            "max_drawdown": 0.0,
            "peak_date": None,
            "trough_date": None,
            "max_drawdown_date": None,
            "recovery_date": None,
            "is_recovered": True,
            "days_to_trough": None,
            "days_to_recovery": None,
            "time_under_water_days": 0,
        }

    trough_idx = cast(pd.Timestamp, drawdown.idxmin())
    peak_idx = cast(pd.Timestamp, wealth.loc[:trough_idx].idxmax())
    max_drawdown = _as_number(cast(float, drawdown.loc[trough_idx] * 100))
    peak_value = _as_number(cast(float, peak.loc[trough_idx]))
    post_trough_wealth = wealth.loc[trough_idx:]
    recovery_candidates = post_trough_wealth[post_trough_wealth >= peak_value]
    recovery_idx = (
        cast(pd.Timestamp, recovery_candidates.index[0]) if not recovery_candidates.empty else None
    )
    days_to_trough = int((trough_idx - peak_idx).days)
    if recovery_idx is not None:
        days_to_recovery = int((recovery_idx - trough_idx).days)
        time_under_water_days = int((recovery_idx - peak_idx).days)
        recovery_date = str(recovery_idx.date())
    else:
        days_to_recovery = None
        time_under_water_days = int((wealth.index[-1] - peak_idx).days)
        recovery_date = None
    trough_date = str(trough_idx.date())
    return {
        "max_drawdown": max_drawdown,
        "peak_date": str(peak_idx.date()),
        "trough_date": trough_date,
        "max_drawdown_date": trough_date,
        "recovery_date": recovery_date,
        "is_recovered": recovery_idx is not None,
        "days_to_trough": days_to_trough,
        "days_to_recovery": days_to_recovery,
        "time_under_water_days": time_under_water_days,
    }


def _var_historical(returns: pd.Series, confidence: float) -> float:
    alpha = 1.0 - confidence
    return cast(float, np.percentile(returns, alpha * 100))


def _var_gaussian(returns: pd.Series, confidence: float) -> float:
    alpha = 1.0 - confidence
    z_score = NormalDist().inv_cdf(alpha)
    return _as_number(returns.mean() + returns.std(ddof=1) * z_score)


def _var_cornish_fisher(returns: pd.Series, confidence: float) -> float:
    alpha = 1.0 - confidence
    z_score = NormalDist().inv_cdf(alpha)
    skew = _as_number(cast(float, returns.skew()))
    kurt = _as_number(cast(float, returns.kurt()))
    z_cf = z_score
    z_cf += ((z_score**2) - 1) * skew / 6
    z_cf += ((z_score**3) - 3 * z_score) * kurt / 24
    z_cf -= ((2 * z_score**3) - 5 * z_score) * (skew**2) / 36
    return _as_number(returns.mean() + returns.std(ddof=1) * z_cf)


def _calculate_var_by_method(returns: pd.Series, method: str, confidence: float) -> float:
    if method == "HISTORICAL":
        return _var_historical(returns, confidence)
    if method == "GAUSSIAN":
        return _var_gaussian(returns, confidence)
    if method == "CORNISH_FISHER":
        return _var_cornish_fisher(returns, confidence)
    raise ValueError(f"Unsupported VaR method: {method}")


def _expected_shortfall(returns: pd.Series, var_value: float) -> float:
    tail = returns[returns <= var_value]
    if tail.empty:
        return _as_number(var_value)
    return _as_number(tail.mean())


def _beta(portfolio: pd.Series, benchmark: pd.Series) -> tuple[float, RiskMetricDetails]:
    covariance = np.cov(portfolio, benchmark, ddof=1)
    denominator = covariance[1, 1]
    if np.isclose(denominator, 0.0):
        raise ValueError("Benchmark variance is zero")
    covariance_pb = _as_number(covariance[0, 1])
    benchmark_variance = _as_number(denominator)
    return (
        _as_number(covariance_pb / benchmark_variance),
        {
            "aligned_observation_count": int(portfolio.count()),
            "portfolio_mean_return": _as_number(portfolio.mean() / 100),
            "benchmark_mean_return": _as_number(benchmark.mean() / 100),
            "covariance": covariance_pb,
            "benchmark_variance": benchmark_variance,
        },
    )


def _tracking_error(
    portfolio: pd.Series, benchmark: pd.Series, annual_factor: int
) -> tuple[float, RiskMetricDetails]:
    active = portfolio - benchmark
    active_std = _as_number(active.std(ddof=1))
    annualized_tracking_error = _as_number(active_std * sqrt(annual_factor))
    return (
        annualized_tracking_error,
        {
            "aligned_observation_count": int(active.count()),
            "annualization_factor": annual_factor,
            "portfolio_mean_return": _as_number(portfolio.mean() / 100),
            "benchmark_mean_return": _as_number(benchmark.mean() / 100),
            "active_mean_return": _as_number(active.mean() / 100),
            "active_volatility": active_std / 100,
            "annualized_tracking_error": annualized_tracking_error / 100,
        },
    )


def _information_ratio(
    portfolio: pd.Series, benchmark: pd.Series, annual_factor: int
) -> tuple[float, RiskMetricDetails]:
    active = portfolio - benchmark
    tracking_err = active.std(ddof=1)
    if np.isclose(tracking_err, 0.0):
        raise ValueError("Tracking error is zero")
    active_mean = _as_number(active.mean() / 100)
    tracking_error = _as_number(tracking_err / 100)
    annualized_active_return = _as_number(active_mean * annual_factor)
    annualized_tracking_error = _as_number(tracking_error * sqrt(annual_factor))
    return (
        _as_number((active.mean() / tracking_err) * sqrt(annual_factor)),
        {
            "aligned_observation_count": int(active.count()),
            "annualization_factor": annual_factor,
            "portfolio_mean_return": _as_number(portfolio.mean() / 100),
            "benchmark_mean_return": _as_number(benchmark.mean() / 100),
            "active_mean_return": active_mean,
            "tracking_error": tracking_error,
            "annualized_active_return": annualized_active_return,
            "annualized_tracking_error": annualized_tracking_error,
        },
    )


def _calculate_benchmark_metric(
    metric_name: str, portfolio: pd.Series, benchmark: pd.Series, annual_factor: int
) -> tuple[float, RiskMetricDetails]:
    if metric_name == "BETA":
        return _beta(portfolio, benchmark)
    if metric_name == "TRACKING_ERROR":
        return _tracking_error(portfolio, benchmark, annual_factor)
    if metric_name == "INFORMATION_RATIO":
        return _information_ratio(portfolio, benchmark, annual_factor)
    raise ValueError(f"Unsupported benchmark metric: {metric_name}")


def _require_data(series: pd.Series, minimum: int = 2) -> None:
    if len(series.dropna()) < minimum:
        raise ValueError("Insufficient data")


BENCHMARK_METRICS = RISK_METRICS_REQUIRING_BENCHMARK
