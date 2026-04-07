from __future__ import annotations

import pytest

from app.services.stateful_returns_series_parser import (
    decimal_return_to_percentage_points,
    extract_required_portfolio_returns,
    extract_series_payload,
    to_return_points,
)


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


def test_extract_series_payload_requires_series_object() -> None:
    with pytest.raises(ValueError, match="missing 'series' object"):
        extract_series_payload({})


def test_extract_required_portfolio_returns_requires_non_empty_portfolio_series() -> None:
    with pytest.raises(ValueError, match="returned no portfolio returns"):
        extract_required_portfolio_returns({"series": {"portfolio_returns": []}})
