from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.contracts.risk import ReturnPoint
from app.upstream_errors import invalid_upstream_payload, missing_upstream_data


def is_trading_day(value: date) -> bool:
    return value.weekday() < 5


def decimal_return_to_percentage_points(value: Any) -> float:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/returns/series",
            message=f"Invalid return value from lotus-performance: {value}",
        ) from exc
    if not decimal_value.is_finite():
        # Decimal("NaN") and Decimal("Infinity") parse successfully and would flow into
        # covariance as non-finite floats; a non-finite return is producer corruption.
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/returns/series",
            message=f"Non-finite return value from lotus-performance: {value}",
        )
    return float(decimal_value * Decimal("100"))


def to_return_points(series: Any) -> list[ReturnPoint]:
    if not isinstance(series, list):
        return []
    result: list[ReturnPoint] = []
    seen_dates: set[date] = set()
    for row in series:
        if not isinstance(row, dict):
            continue
        raw_date = row.get("date")
        if not isinstance(raw_date, str):
            continue
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise invalid_upstream_payload(
                service="lotus-performance",
                operation="/integration/returns/series",
                message="Invalid return date from lotus-performance",
                details={"field": "date"},
            ) from exc
        if not is_trading_day(parsed_date):
            continue
        if parsed_date in seen_dates:
            # Two observations for one date are contradictory economics: which return
            # applies is undecidable, and both entering covariance double-counts a day.
            raise invalid_upstream_payload(
                service="lotus-performance",
                operation="/integration/returns/series",
                message="Duplicate return date from lotus-performance",
                details={"field": "date", "date": parsed_date.isoformat()},
            )
        seen_dates.add(parsed_date)
        result.append(
            ReturnPoint(
                date=parsed_date,
                value=decimal_return_to_percentage_points(row.get("return_value")),
            )
        )
    return result


def extract_series_payload(source_response: dict[str, Any]) -> dict[str, Any]:
    series = source_response.get("series")
    if not isinstance(series, dict):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/returns/series",
            message="lotus-performance returns-series payload missing 'series' object",
        )
    return series


def extract_required_portfolio_returns(
    source_response: dict[str, Any],
) -> tuple[dict[str, Any], list[ReturnPoint]]:
    series = extract_series_payload(source_response)
    portfolio_points = to_return_points(series.get("portfolio_returns"))
    if not portfolio_points:
        raise missing_upstream_data(
            service="lotus-performance",
            operation="/integration/returns/series",
            message="lotus-performance returns-series returned no portfolio returns",
        )
    return series, portfolio_points
