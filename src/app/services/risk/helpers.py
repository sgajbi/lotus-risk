from __future__ import annotations

from datetime import date
from statistics import NormalDist
from typing import cast

import numpy as np
import pandas as pd

from app.services.risk.benchmark_metrics import (
    BENCHMARK_METRICS,
    RISK_METRICS_REQUIRING_BENCHMARK,
    RiskMetricDetails,
)
from app.services.risk.benchmark_metrics import (
    beta as _beta,
)
from app.services.risk.benchmark_metrics import (
    calculate_benchmark_metric as _calculate_benchmark_metric,
)
from app.services.risk.benchmark_metrics import (
    information_ratio as _information_ratio,
)
from app.services.risk.drawdown_details import drawdown_details as _drawdown
from app.services.risk.numeric import as_number as _as_number
from app.services.risk.period_resolution import (
    resolve_period,
    resolve_period_bounds,
)

RISK_METRICS_REQUIRING_RISK_FREE = {"SHARPE"}
_CORNISH_FISHER_MINIMUM_OBSERVATIONS = 4
LOG_RETURN_UNDEFINED_ERROR = "Log returns are undefined for returns less than or equal to -100%"
RESAMPLING_GAP_ERROR_PREFIX = "Missing return observations in resampling buckets ending"


def _resolve_period(
    period_type: str,
    as_of: date,
    open_date: date,
    *,
    year: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[date, date]:
    return resolve_period(
        period_type,
        as_of,
        open_date,
        year=year,
        from_date=from_date,
        to_date=to_date,
    )


def _resolve_period_bounds(
    period_type: str,
    as_of: date,
    open_date: date,
    *,
    year: int | None,
    from_date: date | None,
    to_date: date | None,
) -> tuple[date, date]:
    return resolve_period_bounds(
        period_type,
        as_of,
        open_date,
        year=year,
        from_date=from_date,
        to_date=to_date,
    )


def _resample_returns(
    returns: pd.Series,
    frequency: str,
) -> pd.Series:
    """Compound populated buckets and refuse gaps bounded by source observations.

    An absent bucket between supplied observations cannot acquire the
    mathematical identity return of zero. Leading and trailing partial buckets
    remain eligible because Risk cannot infer an unprovided market calendar or
    source cadence from a selected period boundary alone.
    """
    if returns.empty:
        return returns
    if frequency == "DAILY":
        return returns
    rule = {"WEEKLY": "W-FRI", "MONTHLY": "ME"}[frequency]

    def _compound_populated_bucket(bucket: pd.Series) -> float:
        observations = bucket.dropna()
        if observations.empty:
            return float("nan")
        observation_values = observations.to_numpy(dtype=float)
        return float((np.prod(1.0 + observation_values / 100.0) - 1.0) * 100.0)

    resampled = returns.resample(rule).apply(_compound_populated_bucket)
    if isinstance(resampled, pd.DataFrame):
        if resampled.shape[1] != 1:
            raise TypeError(f"Unexpected resample result shape: {resampled.shape}")
        resampled = resampled.iloc[:, 0]
    missing_bucket_ends = resampled.index[resampled.isna()]
    if len(missing_bucket_ends):
        formatted_bucket_ends = ", ".join(
            pd.Timestamp(bucket_end).date().isoformat() for bucket_end in missing_bucket_ends
        )
        raise ValueError(f"{RESAMPLING_GAP_ERROR_PREFIX}: {formatted_bucket_ends}")
    return resampled


def _to_log_returns(returns: pd.Series) -> pd.Series:
    if returns.empty:
        return returns
    if (returns <= -100.0).any():
        raise ValueError(LOG_RETURN_UNDEFINED_ERROR)
    return pd.Series(np.log1p(returns / 100) * 100, index=returns.index, name=returns.name)


def _annual_to_periodic(rate: float, annual_factor: int) -> float:
    return float((1.0 + float(rate)) ** (1.0 / float(annual_factor)) - 1.0)


def _var_historical(returns: pd.Series, confidence: float) -> float:
    alpha = 1.0 - confidence
    return cast(float, np.percentile(returns, alpha * 100))


def _var_gaussian(returns: pd.Series, confidence: float) -> float:
    alpha = 1.0 - confidence
    z_score = NormalDist().inv_cdf(alpha)
    return _as_number(returns.mean() + returns.std(ddof=1) * z_score)


def _var_cornish_fisher(returns: pd.Series, confidence: float) -> float:
    _require_data(returns, minimum=_CORNISH_FISHER_MINIMUM_OBSERVATIONS)
    alpha = 1.0 - confidence
    z_score = NormalDist().inv_cdf(alpha)
    skew = _as_number(cast(float, returns.skew()))
    kurt = _as_number(cast(float, returns.kurt()))
    z_cf = z_score
    z_cf += ((z_score**2) - 1) * skew / 6
    z_cf += ((z_score**3) - 3 * z_score) * kurt / 24
    z_cf -= ((2 * z_score**3) - 5 * z_score) * (skew**2) / 36
    var_value = _as_number(returns.mean() + returns.std(ddof=1) * z_cf)
    if not np.isfinite(var_value):
        raise ValueError("Cornish-Fisher VaR is undefined for this sample")
    return var_value


def _calculate_var_by_method(returns: pd.Series, method: str, confidence: float) -> float:
    if method == "HISTORICAL":
        return _var_historical(returns, confidence)
    if method == "GAUSSIAN":
        return _var_gaussian(returns, confidence)
    if method == "CORNISH_FISHER":
        return _var_cornish_fisher(returns, confidence)
    raise ValueError(f"Unsupported VaR method: {method}")


def _expected_shortfall(
    returns: pd.Series,
    var_value: float,  # monetary-float-allow: VaR threshold in return percentage points, not money.
) -> float:
    tail = returns[returns <= var_value]
    if tail.empty:
        return _as_number(var_value)
    return _as_number(tail.mean())


def _require_data(series: pd.Series, minimum: int = 2) -> None:
    if len(series.dropna()) < minimum:
        raise ValueError("Insufficient data")


__all__ = [
    "BENCHMARK_METRICS",
    "LOG_RETURN_UNDEFINED_ERROR",
    "RISK_METRICS_REQUIRING_BENCHMARK",
    "RISK_METRICS_REQUIRING_RISK_FREE",
    "RiskMetricDetails",
    "_annual_to_periodic",
    "_as_number",
    "_beta",
    "_calculate_benchmark_metric",
    "_calculate_var_by_method",
    "_drawdown",
    "_expected_shortfall",
    "_information_ratio",
    "_require_data",
    "_resample_returns",
    "_resolve_period",
    "_resolve_period_bounds",
    "_to_log_returns",
]
