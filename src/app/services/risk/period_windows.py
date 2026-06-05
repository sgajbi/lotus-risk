from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.contracts.risk import RiskStatelessCalculationInput
from app.services.risk import helpers as risk_helpers


@dataclass(frozen=True)
class RiskPeriodWindow:
    name: str
    start: pd.Timestamp
    end: pd.Timestamp
    returns: pd.Series


def risk_period_window(
    *,
    request: RiskStatelessCalculationInput,
    period_index: int,
    returns_df: pd.DataFrame,
) -> RiskPeriodWindow:
    period = request.periods[period_index]
    start, end = risk_helpers._resolve_period(
        period.type,
        request.scope.as_of_date,
        request.portfolio_open_date,
        year=period.year,
        from_date=period.from_date,
        to_date=period.to_date,
    )
    start_timestamp = pd.Timestamp(start)
    end_timestamp = pd.Timestamp(end)
    period_mask = (returns_df.index >= start_timestamp) & (returns_df.index <= end_timestamp)
    return RiskPeriodWindow(
        name=period.name or period.type,
        start=start_timestamp,
        end=end_timestamp,
        returns=returns_df.loc[period_mask, "value"],
    )


__all__ = ["RiskPeriodWindow", "risk_period_window"]
