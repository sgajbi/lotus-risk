from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pandas as pd

from app.services.risk.numeric import as_number


@dataclass(frozen=True)
class DrawdownRecovery:
    recovery_date: str | None
    is_recovered: bool
    days_to_recovery: int | None
    time_under_water_days: int


def empty_drawdown_details() -> dict[str, str | float | None]:
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


def drawdown_recovery(
    *,
    wealth: pd.Series,
    peak_idx: pd.Timestamp,
    trough_idx: pd.Timestamp,
    peak_value: float,  # monetary-float-allow: drawdown wealth ratio peak, not money.
) -> DrawdownRecovery:
    post_trough_wealth = wealth.loc[trough_idx:]
    recovery_candidates = post_trough_wealth[post_trough_wealth >= peak_value]
    recovery_idx = (
        cast(pd.Timestamp, recovery_candidates.index[0]) if not recovery_candidates.empty else None
    )
    if recovery_idx is None:
        return DrawdownRecovery(
            recovery_date=None,
            is_recovered=False,
            days_to_recovery=None,
            time_under_water_days=int((wealth.index[-1] - peak_idx).days),
        )
    return DrawdownRecovery(
        recovery_date=str(recovery_idx.date()),
        is_recovered=True,
        days_to_recovery=int((recovery_idx - trough_idx).days),
        time_under_water_days=int((recovery_idx - peak_idx).days),
    )


def drawdown_details(returns: pd.Series) -> dict[str, str | float | None]:
    wealth = (1 + returns / 100).cumprod()
    peak = wealth.cummax()
    drawdown = wealth / peak - 1
    if drawdown.empty:
        return empty_drawdown_details()

    trough_idx = cast(pd.Timestamp, drawdown.idxmin())
    peak_idx = cast(pd.Timestamp, wealth.loc[:trough_idx].idxmax())
    max_drawdown = as_number(cast(float, drawdown.loc[trough_idx] * 100))
    peak_value = as_number(
        cast(float, peak.loc[trough_idx])
    )  # monetary-float-allow: drawdown wealth ratio peak, not money.
    recovery = drawdown_recovery(
        wealth=wealth,
        peak_idx=peak_idx,
        trough_idx=trough_idx,
        peak_value=peak_value,
    )
    days_to_trough = int((trough_idx - peak_idx).days)
    trough_date = str(trough_idx.date())
    return {
        "max_drawdown": max_drawdown,
        "peak_date": str(peak_idx.date()),
        "trough_date": trough_date,
        "max_drawdown_date": trough_date,
        "recovery_date": recovery.recovery_date,
        "is_recovered": recovery.is_recovered,
        "days_to_trough": days_to_trough,
        "days_to_recovery": recovery.days_to_recovery,
        "time_under_water_days": recovery.time_under_water_days,
    }


__all__ = [
    "DrawdownRecovery",
    "drawdown_details",
    "drawdown_recovery",
    "empty_drawdown_details",
]
