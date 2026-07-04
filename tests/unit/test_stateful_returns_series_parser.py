from __future__ import annotations

from datetime import date

import pytest

from app.services.stateful_returns_series_parser import (
    decimal_return_to_percentage_points,
    extract_required_portfolio_returns,
    extract_series_payload,
    is_trading_day,
    to_return_points,
)
from app.upstream_errors import UpstreamServiceError


def test_decimal_return_to_percentage_points_converts_decimal_returns() -> None:
    assert decimal_return_to_percentage_points("0.0125") == 1.25


def test_decimal_return_to_percentage_points_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="Invalid return value"):
        decimal_return_to_percentage_points("not-a-number")


def test_to_return_points_skips_non_dict_and_invalid_date_rows() -> None:
    points = to_return_points(
        [
            {"date": "2025-01-02", "return_value": "0.0010"},
            "invalid-row",
            {"date": 123, "return_value": "0.0010"},
        ]
    )
    assert len(points) == 1
    assert points[0].value == 0.1


def test_to_return_points_rejects_malformed_upstream_dates_as_invalid_response() -> None:
    with pytest.raises(UpstreamServiceError, match="Invalid return date") as exc_info:
        to_return_points([{"date": "not-a-date", "return_value": "0.0010"}])

    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"
    assert exc_info.value.details["category"] == "invalid_response"
    assert exc_info.value.details["field"] == "date"


def test_to_return_points_enforces_trading_day_policy_for_stateful_risk() -> None:
    points = to_return_points(
        [
            {"date": "2026-01-02", "return_value": "0.0010"},
            {"date": "2026-01-03", "return_value": "0.0200"},
            {"date": "2026-01-04", "return_value": "-0.0300"},
            {"date": "2026-01-05", "return_value": "0.0040"},
        ]
    )

    assert [point.date.isoformat() for point in points] == ["2026-01-02", "2026-01-05"]
    assert [point.value for point in points] == [0.1, 0.4]


def test_is_trading_day_uses_business_day_convention() -> None:
    assert is_trading_day(date(2026, 1, 2))
    assert not is_trading_day(date(2026, 1, 3))


def test_extract_series_payload_requires_series_object() -> None:
    with pytest.raises(ValueError, match="missing 'series' object"):
        extract_series_payload({})


def test_extract_required_portfolio_returns_requires_non_empty_portfolio_series() -> None:
    with pytest.raises(ValueError, match="returned no portfolio returns"):
        extract_required_portfolio_returns({"series": {"portfolio_returns": []}})
