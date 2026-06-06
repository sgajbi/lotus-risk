from __future__ import annotations

from datetime import date, timedelta


def resolve_period(
    period_type: str,
    as_of: date,
    open_date: date,
    *,
    year: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[date, date]:
    start, end = resolve_period_bounds(
        period_type,
        as_of,
        open_date,
        year=year,
        from_date=from_date,
        to_date=to_date,
    )
    return max(start, open_date), end


def resolve_period_bounds(
    period_type: str,
    as_of: date,
    open_date: date,
    *,
    year: int | None,
    from_date: date | None,
    to_date: date | None,
) -> tuple[date, date]:
    if period_type == "EXPLICIT":
        return _resolve_explicit_period(from_date=from_date, to_date=to_date)
    if period_type == "YEAR":
        return _resolve_year_period(year)
    if period_type == "YTD":
        return date(as_of.year, 1, 1), as_of
    if period_type == "QTD":
        return _resolve_quarter_to_date_period(as_of)
    if period_type == "MTD":
        return date(as_of.year, as_of.month, 1), as_of
    if period_type in {"1Y", "3Y", "5Y"}:
        return _resolve_trailing_year_period(period_type, as_of)
    if period_type == "SI":
        return open_date, as_of
    raise ValueError(f"Unsupported period type: {period_type}")


def _resolve_explicit_period(
    *,
    from_date: date | None,
    to_date: date | None,
) -> tuple[date, date]:
    if from_date is None or to_date is None:
        raise ValueError("EXPLICIT period requires from/to dates")
    return from_date, to_date


def _resolve_year_period(year: int | None) -> tuple[date, date]:
    if year is None:
        raise ValueError("YEAR period requires year")
    return date(year, 1, 1), date(year, 12, 31)


def _resolve_quarter_to_date_period(as_of: date) -> tuple[date, date]:
    quarter_start_month = (as_of.month - 1) // 3 * 3 + 1
    return date(as_of.year, quarter_start_month, 1), as_of


def _resolve_trailing_year_period(period_type: str, as_of: date) -> tuple[date, date]:
    years = {"1Y": 1, "3Y": 3, "5Y": 5}[period_type]
    return as_of - timedelta(days=365 * years) + timedelta(days=1), as_of


__all__ = ["resolve_period", "resolve_period_bounds"]
