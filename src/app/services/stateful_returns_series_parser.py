from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.contracts.risk import ReturnPoint


def decimal_return_to_percentage_points(value: Any) -> float:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid return value from lotus-performance: {value}") from exc
    return float(decimal_value * Decimal("100"))


def to_return_points(series: Any) -> list[ReturnPoint]:
    if not isinstance(series, list):
        return []
    result: list[ReturnPoint] = []
    for row in series:
        if not isinstance(row, dict):
            continue
        raw_date = row.get("date")
        if not isinstance(raw_date, str):
            continue
        result.append(
            ReturnPoint(
                date=date.fromisoformat(raw_date),
                value=decimal_return_to_percentage_points(row.get("return_value")),
            )
        )
    return result


def extract_series_payload(source_response: dict[str, Any]) -> dict[str, Any]:
    series = source_response.get("series")
    if not isinstance(series, dict):
        raise ValueError("lotus-performance returns-series payload missing 'series' object")
    return series


def extract_required_portfolio_returns(source_response: dict[str, Any]) -> tuple[dict[str, Any], list[ReturnPoint]]:
    series = extract_series_payload(source_response)
    portfolio_points = to_return_points(series.get("portfolio_returns"))
    if not portfolio_points:
        raise ValueError("lotus-performance returns-series returned no portfolio returns")
    return series, portfolio_points
