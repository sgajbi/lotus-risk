from datetime import date

import pytest

from app.services.core_risk_free_series import (
    build_risk_free_series_request,
    to_risk_free_return_points,
)


def test_build_risk_free_series_request_uses_canonical_core_contract() -> None:
    payload = build_risk_free_series_request(
        currency="USD",
        as_of_date=date(2026, 1, 4),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 4),
    )
    assert payload == {
        "currency": "USD",
        "as_of_date": "2026-01-04",
        "series_mode": "annualized_rate_series",
        "window": {
            "start_date": "2026-01-01",
            "end_date": "2026-01-04",
        },
        "frequency": "daily",
    }


def test_to_risk_free_return_points_converts_annualized_rate_to_periodic_percentage_points() -> (
    None
):
    points = to_risk_free_return_points(
        {
            "points": [
                {
                    "series_date": "2026-01-02",
                    "value": "0.0365",
                    "value_convention": "annualized_rate",
                }
            ]
        },
        annualization_basis=365,
    )

    assert len(points) == 1
    assert points[0].date.isoformat() == "2026-01-02"
    assert round(points[0].value, 6) == round(0.009822305067408443, 6)


def test_to_risk_free_return_points_preserves_periodic_return_values() -> None:
    points = to_risk_free_return_points(
        {
            "points": [
                {
                    "series_date": "2026-01-02",
                    "value": "0.0002",
                    "value_convention": "period_return",
                }
            ]
        },
        annualization_basis=252,
    )

    assert len(points) == 1
    assert points[0].value == 0.02


def test_to_risk_free_return_points_rejects_unknown_value_convention() -> None:
    with pytest.raises(ValueError, match="Unsupported risk-free value_convention"):
        to_risk_free_return_points(
            {
                "points": [
                    {
                        "series_date": "2026-01-02",
                        "value": "0.0002",
                        "value_convention": "mystery",
                    }
                ]
            },
            annualization_basis=252,
        )


def test_to_risk_free_return_points_rejects_missing_points_contract() -> None:
    with pytest.raises(ValueError, match="missing 'points' list"):
        to_risk_free_return_points({"points": "bad"}, annualization_basis=252)


def test_to_risk_free_return_points_skips_non_object_and_missing_date_rows() -> None:
    points = to_risk_free_return_points(
        {
            "points": [
                "bad",
                {"value": "0.0001", "value_convention": "period_return"},
                {
                    "series_date": "2026-01-02",
                    "value": "0.0002",
                    "value_convention": "periodic_return",
                },
            ]
        },
        annualization_basis=252,
    )

    assert len(points) == 1
    assert points[0].date.isoformat() == "2026-01-02"
    assert points[0].value == 0.02


def test_to_risk_free_return_points_rejects_invalid_numeric_value() -> None:
    with pytest.raises(ValueError, match="Invalid risk-free value"):
        to_risk_free_return_points(
            {
                "points": [
                    {
                        "series_date": "2026-01-02",
                        "value": "not-a-number",
                        "value_convention": "period_return",
                    }
                ]
            },
            annualization_basis=252,
        )
