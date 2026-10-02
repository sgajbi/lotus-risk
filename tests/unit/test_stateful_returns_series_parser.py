from __future__ import annotations

from datetime import date

import pytest

from app.services.stateful_returns_series_parser import (
    decimal_return_to_percentage_points,
    extract_required_portfolio_returns,
    extract_series_payload,
    extract_stateful_returns_source_evidence,
    is_trading_day,
    normalize_return_points_to_resolved_window,
    to_return_points,
)
from app.upstream_errors import UpstreamServiceError
from tests.support.returns_series_payloads import build_returns_series_response


def test_decimal_return_to_percentage_points_converts_decimal_returns() -> None:
    assert decimal_return_to_percentage_points("0.0125") == 1.25


def test_decimal_return_to_percentage_points_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="Invalid return value"):
        decimal_return_to_percentage_points("not-a-number")


@pytest.mark.parametrize(
    "unusable_row",
    ["invalid-row", {"date": 123, "return_value": "0.0010"}],
)
def test_to_return_points_ignores_non_string_date_rows(unusable_row: object) -> None:
    assert to_return_points([unusable_row]) == []


def test_to_return_points_rejects_malformed_upstream_dates_as_invalid_response() -> None:
    with pytest.raises(UpstreamServiceError, match="Invalid return date") as exc_info:
        to_return_points([{"date": "not-a-date", "return_value": "0.0010"}])

    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"
    assert exc_info.value.details["category"] == "invalid_response"
    assert exc_info.value.details["field"] == "date"


def test_to_return_points_filters_weekend_daily_observations() -> None:
    points = to_return_points(
        [
            {"date": "2026-01-02", "return_value": "0.0100"},
            {"date": "2026-01-03", "return_value": "0.0200"},
        ]
    )

    assert [point.date.isoformat() for point in points] == ["2026-01-02"]


@pytest.mark.parametrize(
    ("frequency", "observation_date"),
    [("WEEKLY", "2026-01-30"), ("MONTHLY", "2026-01-31")],
)
def test_to_return_points_accepts_producer_bucket_dates(
    frequency: str,
    observation_date: str,
) -> None:
    points = to_return_points(
        [{"date": observation_date, "return_value": "0.0200"}],
        frequency=frequency,
    )

    assert points[0].date.isoformat() == observation_date


def test_to_return_points_accepts_maximum_iso_month_end_without_overflow() -> None:
    points = to_return_points(
        [{"date": "9999-12-31", "return_value": "0.0200"}],
        frequency="MONTHLY",
    )

    assert points[0].date == date.max


@pytest.mark.parametrize(
    ("frequency", "bucket_end", "window_end"),
    [
        ("WEEKLY", "2026-01-09", "2026-01-08"),
        ("MONTHLY", "2026-01-31", "2026-01-08"),
    ],
)
def test_trailing_partial_source_bucket_is_admitted_and_normalized_for_consumption(
    frequency: str,
    bucket_end: str,
    window_end: str,
) -> None:
    response = build_returns_series_response(
        portfolio_returns=((bucket_end, "0.0200"),),
        as_of_date=window_end,
        resolved_start_date="2026-01-01",
        resolved_period_label="YTD",
        frequency=frequency,
    )
    points = to_return_points(response["series"]["portfolio_returns"], frequency=frequency)

    extract_stateful_returns_source_evidence(
        response,
        portfolio_id="DEMO_DPM_EUR_001",
        as_of_date=date.fromisoformat(window_end),
        frequency=frequency,
        metric_basis="NET",
        requested_window={"mode": "RELATIVE", "period": "YTD"},
        returned_points=points,
    )
    normalized = normalize_return_points_to_resolved_window(
        response,
        points,
        frequency=frequency,
    )

    assert normalized[0].date == date.fromisoformat(window_end)


def test_normalization_refuses_bucket_that_does_not_overlap_resolved_window() -> None:
    response = build_returns_series_response(
        portfolio_returns=(("2026-02-28", "0.0200"),),
        as_of_date="2026-01-08",
        resolved_start_date="2026-01-01",
        frequency="MONTHLY",
    )
    points = to_return_points(response["series"]["portfolio_returns"], frequency="MONTHLY")

    with pytest.raises(UpstreamServiceError) as exc_info:
        normalize_return_points_to_resolved_window(
            response,
            points,
            frequency="MONTHLY",
        )

    assert exc_info.value.details["field"] == "series.portfolio_returns.date"


def test_minimum_iso_weekly_bucket_is_refused_without_overflow() -> None:
    response = build_returns_series_response(
        portfolio_returns=(("0001-01-05", "0.0200"),),
        as_of_date="2026-01-08",
        resolved_start_date="2026-01-01",
        frequency="WEEKLY",
    )
    points = to_return_points(response["series"]["portfolio_returns"], frequency="WEEKLY")

    with pytest.raises(UpstreamServiceError) as exc_info:
        normalize_return_points_to_resolved_window(
            response,
            points,
            frequency="WEEKLY",
        )

    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"


def test_is_trading_day_uses_business_day_convention() -> None:
    assert is_trading_day(date(2026, 1, 2))
    assert not is_trading_day(date(2026, 1, 3))


def test_extract_series_payload_requires_series_object() -> None:
    with pytest.raises(ValueError, match="missing 'series' object"):
        extract_series_payload({})


def test_extract_required_portfolio_returns_requires_non_empty_portfolio_series() -> None:
    with pytest.raises(ValueError, match="returned no portfolio returns"):
        extract_required_portfolio_returns({"series": {"portfolio_returns": []}})


@pytest.mark.parametrize("raw_value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_upstream_returns_are_refused_before_statistics(raw_value: str) -> None:
    """Decimal("NaN")/("Infinity") parse successfully; before #291 they flowed into
    covariance as non-finite floats. They are producer corruption and refuse as such."""
    with pytest.raises(UpstreamServiceError) as excinfo:
        decimal_return_to_percentage_points(raw_value)
    assert excinfo.value.code == "UPSTREAM_INVALID_RESPONSE"


def test_duplicate_upstream_return_dates_are_refused() -> None:
    """Two observations for one date are contradictory economics: before #291 both
    entered the series and double-counted the day."""
    with pytest.raises(UpstreamServiceError) as excinfo:
        to_return_points(
            [
                {"date": "2026-01-05", "return_value": "0.01"},
                {"date": "2026-01-05", "return_value": "0.03"},
            ]
        )
    assert excinfo.value.code == "UPSTREAM_INVALID_RESPONSE"
    assert excinfo.value.details.get("date") == "2026-01-05"


def test_stateful_source_evidence_requires_matching_identity_and_reconciled_coverage() -> None:
    response = build_returns_series_response(
        portfolio_returns=(("2026-01-02", "0.01"), ("2026-01-05", "-0.02")),
        as_of_date="2026-01-05",
    )

    evidence = extract_stateful_returns_source_evidence(
        response,
        portfolio_id="DEMO_DPM_EUR_001",
        as_of_date=date(2026, 1, 5),
        frequency="DAILY",
        metric_basis="NET",
    )

    assert str(evidence.calculation_id) == "00000000-0000-4000-8000-000000000001"
    assert evidence.coverage_ratio == 1.0
    response["metric_basis"] = "GROSS"
    with pytest.raises(UpstreamServiceError) as excinfo:
        extract_stateful_returns_source_evidence(
            response,
            portfolio_id="DEMO_DPM_EUR_001",
            as_of_date=date(2026, 1, 5),
            frequency="DAILY",
            metric_basis="NET",
        )
    assert excinfo.value.code == "UPSTREAM_INVALID_RESPONSE"
    assert excinfo.value.details["field"] == "metric_basis"


def test_stateful_source_evidence_refuses_unsupported_contract_version() -> None:
    response = build_returns_series_response(
        portfolio_returns=(("2026-01-02", "0.01"),),
        as_of_date="2026-01-02",
    )
    response["contract_version"] = "v2"

    with pytest.raises(UpstreamServiceError) as excinfo:
        extract_stateful_returns_source_evidence(
            response,
            portfolio_id="DEMO_DPM_EUR_001",
            as_of_date=date(2026, 1, 2),
            frequency="DAILY",
            metric_basis="NET",
        )

    assert excinfo.value.code == "UPSTREAM_INVALID_RESPONSE"
    assert excinfo.value.details["field"] == "source_qualification"


def test_stateful_source_evidence_binds_coverage_to_consumed_points() -> None:
    response = build_returns_series_response(
        portfolio_returns=(("2026-01-02", "0.01"), ("2026-01-05", "-0.02")),
        as_of_date="2026-01-05",
        returned_points=3,
        requested_points=3,
    )

    with pytest.raises(UpstreamServiceError) as exc_info:
        extract_stateful_returns_source_evidence(
            response,
            portfolio_id="DEMO_DPM_EUR_001",
            as_of_date=date(2026, 1, 5),
            frequency="DAILY",
            metric_basis="NET",
            returned_points=to_return_points(response["series"]["portfolio_returns"]),
        )

    assert exc_info.value.details["field"] == "diagnostics.coverage.returned_points"


def test_stateful_source_evidence_binds_relative_period_label() -> None:
    response = build_returns_series_response(
        portfolio_returns=(("2026-01-02", "0.01"),),
        as_of_date="2026-01-05",
        resolved_period_label="YTD",
    )

    with pytest.raises(UpstreamServiceError) as exc_info:
        extract_stateful_returns_source_evidence(
            response,
            portfolio_id="DEMO_DPM_EUR_001",
            as_of_date=date(2026, 1, 5),
            frequency="DAILY",
            metric_basis="NET",
            requested_window={"mode": "RELATIVE", "period": "SI"},
            returned_points=to_return_points(response["series"]["portfolio_returns"]),
        )

    assert exc_info.value.details["field"] == "resolved_window"


def test_stateful_source_evidence_refuses_points_outside_resolved_window() -> None:
    response = build_returns_series_response(
        portfolio_returns=(("2025-12-31", "0.01"), ("2026-01-02", "-0.02")),
        as_of_date="2026-01-06",
        resolved_start_date="2026-01-01",
        resolved_period_label="YTD",
    )
    returned_points = to_return_points(response["series"]["portfolio_returns"])

    with pytest.raises(UpstreamServiceError) as exc_info:
        extract_stateful_returns_source_evidence(
            response,
            portfolio_id="DEMO_DPM_EUR_001",
            as_of_date=date(2026, 1, 6),
            frequency="DAILY",
            metric_basis="NET",
            requested_window={"mode": "RELATIVE", "period": "YTD"},
            returned_points=returned_points,
        )

    assert exc_info.value.details["field"] == "series.portfolio_returns.date"
