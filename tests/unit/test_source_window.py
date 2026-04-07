from __future__ import annotations

from datetime import date

from app.contracts.risk import RiskRequestPeriod
from app.services.source_window import build_returns_series_window


def test_build_returns_series_window_resolves_longest_explicit_window() -> None:
    periods = [
        RiskRequestPeriod.model_validate({"type": "YTD", "name": "YTD"}),
        RiskRequestPeriod.model_validate({"type": "MTD", "name": "MTD"}),
        RiskRequestPeriod.model_validate(
            {
                "type": "EXPLICIT",
                "name": "explicit_q1",
                "from_date": "2026-02-01",
                "to_date": "2026-03-15",
            }
        ),
    ]

    window = build_returns_series_window(periods=periods, as_of_date=date(2026, 3, 31))
    assert window == {
        "mode": "EXPLICIT",
        "from_date": "2026-01-01",
        "to_date": "2026-03-31",
    }


def test_build_returns_series_window_preserves_since_inception_requests() -> None:
    periods = [RiskRequestPeriod.model_validate({"type": "SI", "name": "SI"})]

    window = build_returns_series_window(periods=periods, as_of_date=date(2026, 3, 31))

    assert window == {"mode": "RELATIVE", "period": "SI"}
