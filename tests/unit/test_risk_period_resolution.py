from datetime import date

import pytest

from app.services.risk.period_resolution import resolve_period, resolve_period_bounds


def test_resolve_period_clips_start_to_portfolio_open_date() -> None:
    assert resolve_period(
        "YTD",
        date(2026, 3, 31),
        date(2026, 2, 15),
    ) == (date(2026, 2, 15), date(2026, 3, 31))


def test_resolve_period_bounds_cover_supported_period_types() -> None:
    assert resolve_period_bounds(
        "MTD",
        date(2026, 5, 17),
        date(2020, 1, 1),
        year=None,
        from_date=None,
        to_date=None,
    ) == (date(2026, 5, 1), date(2026, 5, 17))
    assert resolve_period_bounds(
        "QTD",
        date(2026, 5, 17),
        date(2020, 1, 1),
        year=None,
        from_date=None,
        to_date=None,
    ) == (date(2026, 4, 1), date(2026, 5, 17))
    assert resolve_period_bounds(
        "1Y",
        date(2026, 5, 17),
        date(2020, 1, 1),
        year=None,
        from_date=None,
        to_date=None,
    ) == (date(2025, 5, 18), date(2026, 5, 17))
    assert resolve_period_bounds(
        "YEAR",
        date(2026, 5, 17),
        date(2020, 1, 1),
        year=2024,
        from_date=None,
        to_date=None,
    ) == (date(2024, 1, 1), date(2024, 12, 31))
    assert resolve_period_bounds(
        "EXPLICIT",
        date(2026, 5, 17),
        date(2020, 1, 1),
        year=None,
        from_date=date(2026, 1, 2),
        to_date=date(2026, 1, 9),
    ) == (date(2026, 1, 2), date(2026, 1, 9))


def test_resolve_period_rejects_missing_or_unknown_inputs() -> None:
    with pytest.raises(ValueError, match="EXPLICIT period requires"):
        resolve_period("EXPLICIT", date(2026, 3, 31), date(2020, 1, 1))
    with pytest.raises(ValueError, match="YEAR period requires year"):
        resolve_period("YEAR", date(2026, 3, 31), date(2020, 1, 1))
    with pytest.raises(ValueError, match="Unsupported period type"):
        resolve_period("BAD", date(2026, 3, 31), date(2020, 1, 1))
