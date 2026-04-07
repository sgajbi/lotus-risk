from __future__ import annotations

from datetime import date
from typing import Any

from app.contracts.risk import RiskRequestPeriod
from app.services.risk_engine import _resolve_period


def build_returns_series_window(*, periods: list[RiskRequestPeriod], as_of_date: date) -> dict[str, Any]:
    if any(period.type == "SI" for period in periods):
        return {"mode": "RELATIVE", "period": "SI"}

    resolved_ranges = [
        _resolve_period(
            period.type,
            as_of_date,
            date.min,
            year=period.year,
            from_date=period.from_date,
            to_date=period.to_date,
        )
        for period in periods
    ]
    start_date = min(start for start, _ in resolved_ranges)
    end_date = max(end for _, end in resolved_ranges)
    return {
        "mode": "EXPLICIT",
        "from_date": start_date.isoformat(),
        "to_date": end_date.isoformat(),
    }
