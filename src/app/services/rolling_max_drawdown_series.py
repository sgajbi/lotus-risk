from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_max_drawdown_metric(
    series_decimal: pd.Series,
    *,
    window_length: int,
    min_obs: int,
) -> pd.Series:
    return series_decimal.rolling(window=window_length, min_periods=min_obs).apply(
        rolling_max_drawdown,
        raw=True,
    )


def rolling_max_drawdown(window_decimal_returns: np.ndarray) -> float:
    wealth = np.cumprod(1.0 + window_decimal_returns)
    # Every rolling window is an independent wealth interval with opening
    # wealth/peak one.  Do not let a first-window loss disappear merely because
    # the pre-window baseline has no observation date.
    running_peak = np.maximum.accumulate(np.maximum(wealth, 1.0))
    drawdown = wealth / running_peak - 1.0
    return float(np.min(drawdown))


__all__ = [
    "rolling_max_drawdown",
    "rolling_max_drawdown_metric",
]
