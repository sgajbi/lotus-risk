from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.contracts.risk import ReturnPoint
from app.upstream_errors import invalid_upstream_payload


_PERIODIC_VALUE_CONVENTIONS = {
    "period_return",
    "periodic_return",
    "daily_return",
    "return_series",
}
_ANNUALIZED_VALUE_CONVENTIONS = {
    "annualized_rate",
    "annual_rate",
}


def build_risk_free_series_request(
    *,
    currency: str,
    as_of_date: date,
    start_date: date,
    end_date: date,
    series_mode: str = "annualized_rate_series",
) -> dict[str, Any]:
    return {
        "currency": currency,
        "as_of_date": as_of_date.isoformat(),
        "series_mode": series_mode,
        "window": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "frequency": "daily",
    }


def _annual_to_periodic(rate: Decimal, annualization_basis: int) -> Decimal:
    return Decimal((1.0 + float(rate)) ** (1.0 / float(annualization_basis)) - 1.0)


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise invalid_upstream_payload(
            service="lotus-core",
            operation="/integration/reference/risk-free-series",
            message=f"Invalid risk-free value from lotus-core: {value}",
        ) from exc


def _parse_periodic_return(row: dict[str, Any], *, annualization_basis: int) -> float:
    value_convention = str(row.get("value_convention") or "").strip().lower()
    raw_value = _to_decimal(row.get("value"))

    if value_convention in _PERIODIC_VALUE_CONVENTIONS:
        periodic_decimal = raw_value
    elif value_convention in _ANNUALIZED_VALUE_CONVENTIONS:
        periodic_decimal = _annual_to_periodic(raw_value, annualization_basis)
    else:
        raise invalid_upstream_payload(
            service="lotus-core",
            operation="/integration/reference/risk-free-series",
            message=(
                "Unsupported risk-free value_convention from lotus-core: "
                f"{row.get('value_convention')}"
            ),
        )

    return float(periodic_decimal * Decimal("100"))


def to_risk_free_return_points(
    payload: dict[str, Any],
    *,
    annualization_basis: int,
) -> list[ReturnPoint]:
    points = payload.get("points")
    if not isinstance(points, list):
        raise invalid_upstream_payload(
            service="lotus-core",
            operation="/integration/reference/risk-free-series",
            message="lotus-core risk-free-series payload missing 'points' list",
        )

    result: list[ReturnPoint] = []
    for row in points:
        if not isinstance(row, dict):
            continue
        raw_date = row.get("series_date")
        if not isinstance(raw_date, str):
            continue
        result.append(
            ReturnPoint(
                date=date.fromisoformat(raw_date),
                value=_parse_periodic_return(row, annualization_basis=annualization_basis),
            )
        )
    return result
