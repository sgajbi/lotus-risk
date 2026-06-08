from __future__ import annotations

from datetime import date
from math import sqrt

import numpy as np
import pandas as pd

from app.contracts.risk import RiskValue
from app.services.risk import benchmark_metrics
from app.services.risk import helpers as risk_helpers

RiskMetricDetails = risk_helpers.RiskMetricDetails


def metric_error(message: str) -> RiskValue:
    return RiskValue(value=None, details={"error": message})


def calculate_volatility(
    *,
    metric_series: pd.Series,
    annual_factor: int,
) -> RiskValue:
    risk_helpers._require_data(metric_series)
    standard_deviation = risk_helpers._as_number(metric_series.std(ddof=1) / 100)
    return RiskValue(
        value=risk_helpers._as_number(standard_deviation * sqrt(annual_factor) * 100),
        details={
            "observation_count": int(metric_series.count()),
            "standard_deviation": standard_deviation,
            "annualization_factor": annual_factor,
        },
    )


def calculate_drawdown(*, drawdown_series: pd.Series) -> RiskValue:
    drawdown_data = risk_helpers._drawdown(drawdown_series)
    drawdown_value = drawdown_data.get("max_drawdown")
    return RiskValue(
        value=(
            risk_helpers._as_number(drawdown_value)
            if isinstance(drawdown_value, (int, float))  # monetary-float-allow
            else None
        ),
        details=drawdown_data,
    )


def calculate_sharpe(
    *,
    metric_series: pd.Series,
    periodic_rf: float,
    annual_factor: int,
) -> RiskValue:
    risk_helpers._require_data(metric_series)
    denominator = metric_series.std(ddof=1)
    if np.isclose(denominator, 0.0):
        raise ValueError("Zero volatility")
    mean_return = risk_helpers._as_number(metric_series.mean() / 100)
    excess_return = risk_helpers._as_number(mean_return - periodic_rf)
    sharpe = (excess_return / (denominator / 100)) * sqrt(annual_factor)
    return RiskValue(
        value=risk_helpers._as_number(sharpe),
        details={
            "observation_count": int(metric_series.count()),
            "annualization_factor": annual_factor,
            "mean_return": mean_return,
            "periodic_risk_free_rate": periodic_rf,
            "excess_return": excess_return,
            "annualized_excess_return": risk_helpers._as_number(excess_return * annual_factor),
            "volatility": risk_helpers._as_number(denominator / 100),
        },
    )


def calculate_sortino(
    *,
    metric_series: pd.Series,
    periodic_mar: float,
    annual_factor: int,
    mar_annual_rate: float,
) -> RiskValue:
    risk_helpers._require_data(metric_series)
    downside = (metric_series / 100) - periodic_mar
    downside = downside[downside < 0]
    if downside.empty:
        raise ValueError("No downside observations")
    downside_count = int(downside.count())
    downside_deviation = risk_helpers._as_number(np.sqrt((downside**2).mean()))
    mean_return = risk_helpers._as_number(metric_series.mean() / 100)
    excess_return = risk_helpers._as_number(mean_return - periodic_mar)
    sortino = (excess_return / downside_deviation) * sqrt(annual_factor)
    return RiskValue(
        value=risk_helpers._as_number(sortino),
        details={
            "observation_count": int(metric_series.count()),
            "annualization_factor": annual_factor,
            "mar_annual_rate": mar_annual_rate,
            "periodic_mar": periodic_mar,
            "mean_return": mean_return,
            "excess_return": excess_return,
            "annualized_excess_return": risk_helpers._as_number(excess_return * annual_factor),
            "downside_observation_count": downside_count,
            "downside_deviation": downside_deviation,
        },
    )


def calculate_var(
    *,
    metric_series: pd.Series,
    method: str,
    confidence: float,
    horizon_days: int,
    include_expected_shortfall: bool,
) -> RiskValue:
    risk_helpers._require_data(metric_series)
    base_var = risk_helpers._calculate_var_by_method(metric_series, method, confidence)
    horizon_scale_factor = risk_helpers._as_number(sqrt(horizon_days))
    scaled_var = risk_helpers._as_number(base_var * horizon_scale_factor)
    tail_observation_count = int((metric_series <= base_var).sum())
    var_details: RiskMetricDetails = {
        "method": method,
        "confidence": confidence,
        "tail_probability": risk_helpers._as_number(1.0 - confidence),
        "base_horizon_days": 1,
        "horizon_days": horizon_days,
        "horizon_scale_method": "SQRT_TIME",
        "horizon_scale_factor": horizon_scale_factor,
        "include_expected_shortfall": include_expected_shortfall,
        "base_var": base_var,
        "observation_count": int(metric_series.count()),
        "tail_observation_count": tail_observation_count,
    }
    if include_expected_shortfall:
        base_es = risk_helpers._expected_shortfall(metric_series, base_var)
        var_details["base_expected_shortfall"] = base_es
        var_details["expected_shortfall_observation_count"] = tail_observation_count
        var_details["expected_shortfall"] = risk_helpers._as_number(base_es * horizon_scale_factor)
    return RiskValue(value=scaled_var, details=var_details)


def align_and_resample_benchmark(
    *,
    benchmark_df: pd.DataFrame,
    start: date,
    end: date,
    frequency: str,
    use_log_returns: bool,
) -> pd.Series:
    if benchmark_df.empty:
        return pd.Series(dtype=float)
    benchmark_period = benchmark_df.loc[
        (benchmark_df.index >= pd.Timestamp(start)) & (benchmark_df.index <= pd.Timestamp(end)),
        "value",
    ]
    benchmark_period = risk_helpers._resample_returns(benchmark_period, frequency)
    if use_log_returns:
        benchmark_period = risk_helpers._to_log_returns(benchmark_period)
    return benchmark_period


def resolve_aligned_benchmark_series(
    *,
    metric_series: pd.Series,
    benchmark_series: pd.Series,
) -> pd.DataFrame:
    return pd.merge(
        metric_series.to_frame("portfolio"),
        benchmark_series.to_frame("benchmark"),
        left_index=True,
        right_index=True,
        how="inner",
    )


def resolve_benchmark_metric_value(
    *,
    metric_name: str,
    aligned_portfolio_series: pd.Series,
    aligned_benchmark_series: pd.Series,
    annual_factor: int,
) -> RiskValue:
    value, details = benchmark_metrics.calculate_benchmark_metric(
        metric_name,
        aligned_portfolio_series,
        aligned_benchmark_series,
        annual_factor,
    )
    return RiskValue(value=value, details=details)


def prepare_benchmark_context(
    *,
    benchmark_df_empty: bool,
    aligned_count: int,
    benchmark_metrics: list[str],
) -> dict[str, str | bool | int | list[str]]:
    return {
        "requested": True,
        "available": not benchmark_df_empty,
        "aligned": aligned_count > 0,
        "reason": (
            "BENCHMARK_UNAVAILABLE"
            if benchmark_df_empty
            else ("NO_ALIGNED_OBSERVATIONS" if aligned_count == 0 else "APPLIED")
        ),
        "requested_metric_count": len(benchmark_metrics),
        "requested_metrics": list(benchmark_metrics),
    }
