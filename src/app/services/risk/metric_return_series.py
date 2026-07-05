from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from app.contracts.risk import RiskValue
from app.services.risk import helpers as risk_helpers
from app.services.risk.metric_calculators import metric_error

NON_DRAWDOWN_RETURN_METRICS = {"VOLATILITY", "SHARPE", "SORTINO", "VAR"}


@dataclass(frozen=True)
class MetricReturnSeriesResolution:
    series: pd.Series
    error: str | None = None


def resolve_metric_return_series(
    *,
    period_returns: pd.Series,
    frequency: str,
    use_log_returns: bool,
) -> MetricReturnSeriesResolution:
    try:
        metric_series = risk_helpers._resample_returns(period_returns, frequency)
        if use_log_returns:
            metric_series = risk_helpers._to_log_returns(metric_series)
    except ValueError as exc:
        return MetricReturnSeriesResolution(series=pd.Series(dtype=float), error=str(exc))
    return MetricReturnSeriesResolution(series=metric_series)


def metric_series_error_map(
    *,
    metrics: Sequence[str],
    message: str,
) -> dict[str, RiskValue]:
    return {
        metric_name: metric_error(message)
        for metric_name in NON_DRAWDOWN_RETURN_METRICS
        if metric_name in metrics
    }


__all__ = [
    "MetricReturnSeriesResolution",
    "metric_series_error_map",
    "resolve_metric_return_series",
]
