from __future__ import annotations

import math
import statistics
from copy import deepcopy
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.main import app
from tests.support.app_runtime import override_app_runtime
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import build_returns_series_response

_RETURNS = (
    ("2026-01-02", "0.0100"),
    ("2026-01-05", "-0.0200"),
    ("2026-01-06", "0.0050"),
)


def _request(route: str) -> dict[str, Any]:
    common: dict[str, Any] = {
        "portfolio_id": "DEMO_DPM_EUR_001",
        "as_of_date": "2026-01-06",
        "net_or_gross": "NET",
        "periods": [{"type": "YTD", "name": "YTD"}],
    }
    if route.endswith("rolling-metrics"):
        common["rolling_options"] = {
            "window_lengths": [2],
            "metrics": ["ROLLING_VOLATILITY"],
            "include_time_series": True,
        }
    else:
        common["metrics"] = ["VOLATILITY"]
    return {"input_mode": "stateful", "stateful_input": common}


def _post(route: str, source_response: dict[str, Any]) -> Response:
    client = RecordingLotusPerformanceClient(response_payload=source_response)
    with override_app_runtime(lotus_performance_client=client):
        return cast(
            Response,
            TestClient(app).post(
                route,
                headers={"X-Tenant-Id": "tenant-a", "X-Correlation-Id": "corr-source"},
                json=_request(route),
            ),
        )


@pytest.mark.parametrize(
    ("frequency", "returns"),
    [
        (
            "WEEKLY",
            (("2026-01-09", "0.0100"), ("2026-01-16", "-0.0200")),
        ),
        (
            "MONTHLY",
            (("2026-01-31", "0.0100"), ("2026-02-28", "-0.0200")),
        ),
    ],
)
def test_stateful_risk_admits_producer_frequency_bucket_dates(
    frequency: str,
    returns: tuple[tuple[str, str], ...],
) -> None:
    source = build_returns_series_response(
        portfolio_returns=returns,
        as_of_date="2026-03-31",
        resolved_start_date="2026-01-01",
        frequency=frequency,
    )
    request = _request("/analytics/risk/calculate")
    stateful = cast(dict[str, Any], request["stateful_input"])
    stateful["as_of_date"] = "2026-03-31"
    stateful["options"] = {"frequency": frequency}
    client = RecordingLotusPerformanceClient(response_payload=source)

    with override_app_runtime(lotus_performance_client=client):
        response = cast(
            Response,
            TestClient(app).post(
                "/analytics/risk/calculate",
                headers={"X-Tenant-Id": "tenant-a"},
                json=request,
            ),
        )

    assert response.status_code == 200
    assert response.json()["metadata"]["source_returns_evidence"]["returned_points"] == 2


@pytest.mark.parametrize(
    ("frequency", "bucket_dates", "as_of_date"),
    [
        ("WEEKLY", ("2025-12-26", "2026-01-02", "2026-01-09"), "2026-01-08"),
        ("MONTHLY", ("2025-11-30", "2025-12-31", "2026-01-31"), "2026-01-08"),
    ],
)
def test_stateful_risk_consumes_trailing_partial_producer_bucket(
    frequency: str,
    bucket_dates: tuple[str, ...],
    as_of_date: str,
) -> None:
    returns = tuple(zip(bucket_dates, ("0.0100", "-0.0200", "0.0300"), strict=True))
    source = build_returns_series_response(
        portfolio_returns=returns,
        as_of_date=as_of_date,
        resolved_start_date=bucket_dates[0],
        frequency=frequency,
    )
    request = _request("/analytics/risk/calculate")
    stateful = cast(dict[str, Any], request["stateful_input"])
    stateful["as_of_date"] = as_of_date
    stateful["periods"] = [
        {"type": "EXPLICIT", "name": "Window", "from_date": bucket_dates[0], "to_date": as_of_date}
    ]
    stateful["options"] = {"frequency": frequency}
    client = RecordingLotusPerformanceClient(response_payload=source)

    with override_app_runtime(lotus_performance_client=client):
        response = cast(
            Response,
            TestClient(app).post(
                "/analytics/risk/calculate",
                headers={"X-Tenant-Id": "tenant-a"},
                json=request,
            ),
        )

    assert response.status_code == 200
    result = response.json()["results"]["Window"]
    assert result["portfolio_observation_count"] == 3
    assert result["metrics"]["VOLATILITY"]["details"]["observation_count"] == 3


@pytest.mark.parametrize(
    "route",
    ["/analytics/risk/calculate", "/analytics/risk/rolling-metrics"],
)
def test_stateful_routes_retain_exact_current_source_evidence(route: str) -> None:
    source = build_returns_series_response(
        portfolio_returns=_RETURNS,
        as_of_date="2026-01-06",
        resolved_start_date="2026-01-01",
    )

    response = _post(route, source)

    assert response.status_code == 200
    body = response.json()
    evidence = body["metadata"]["source_returns_evidence"]
    assert evidence == {
        "source_service": "lotus-performance",
        "calculation_id": "00000000-0000-4000-8000-000000000001",
        "contract_version": "v1",
        "input_fingerprint": "sha256:" + "1" * 64,
        "calculation_hash": "sha256:" + "2" * 64,
        "freshness": "current",
        "requested_points": 3,
        "returned_points": 3,
        "missing_points": 0,
        "coverage_ratio": 1.0,
    }
    assert body["metadata"]["calculation_supportability"]["state"] == "ready"
    if route.endswith("calculate"):
        expected = statistics.stdev([1.0, -2.0, 0.5]) * math.sqrt(252)
        assert body["results"]["YTD"]["metrics"]["VOLATILITY"]["value"] == pytest.approx(expected)
    else:
        series = body["results"]["YTD"]["window_results"][0]["metric_series"]
        assert any(
            point["metric_values"]["ROLLING_VOLATILITY"] > 0
            for point in series
            if point["metric_values"]["ROLLING_VOLATILITY"] is not None
        )


def test_stateful_risk_filters_calendar_weekends_before_coverage_reconciliation() -> None:
    source = build_returns_series_response(
        portfolio_returns=(
            ("2026-01-02", "0.0100"),
            ("2026-01-03", "0.0400"),
            ("2026-01-05", "-0.0200"),
            ("2026-01-06", "0.0050"),
        ),
        as_of_date="2026-01-06",
        resolved_start_date="2026-01-01",
        returned_points=3,
        requested_points=3,
    )

    response = _post("/analytics/risk/calculate", source)

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["source_returns_evidence"]["returned_points"] == 3
    assert body["results"]["YTD"]["portfolio_observation_count"] == 3


@pytest.mark.parametrize(
    ("freshness", "missing_points", "expected_state", "expected_reason"),
    [
        ("stale", 0, "stale", "stale_source_observations"),
        ("current", 1, "degraded", "calculation_quality_issue"),
    ],
)
@pytest.mark.parametrize(
    "route",
    ["/analytics/risk/calculate", "/analytics/risk/rolling-metrics"],
)
def test_stateful_routes_compose_source_qualification_without_dropping_figures(
    route: str,
    freshness: str,
    missing_points: int,
    expected_state: str,
    expected_reason: str,
) -> None:
    source = build_returns_series_response(
        portfolio_returns=_RETURNS,
        as_of_date="2026-01-06",
        resolved_start_date="2026-01-01",
        freshness=freshness,
        missing_points=missing_points,
    )

    response = _post(route, source)

    assert response.status_code == 200
    supportability = response.json()["metadata"]["calculation_supportability"]
    assert supportability["state"] == expected_state
    assert supportability["reason"] == expected_reason
    assert response.json()["results"]["YTD"]


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("portfolio_id", "OTHER_PORTFOLIO"),
        ("as_of_date", "2026-01-05"),
        ("frequency", "MONTHLY"),
        ("metric_basis", "GROSS"),
    ],
)
@pytest.mark.parametrize(
    "route",
    ["/analytics/risk/calculate", "/analytics/risk/rolling-metrics"],
)
def test_stateful_routes_refuse_mismatched_source_identity(
    route: str,
    field: str,
    wrong_value: str,
) -> None:
    source = build_returns_series_response(
        portfolio_returns=_RETURNS,
        as_of_date="2026-01-06",
        resolved_start_date="2026-01-01",
    )
    source[field] = wrong_value

    response = _post(route, source)

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_INVALID_RESPONSE"
    assert error["details"]["field"] == field


@pytest.mark.parametrize(
    "route",
    ["/analytics/risk/calculate", "/analytics/risk/rolling-metrics"],
)
def test_stateful_routes_refuse_mismatched_resolved_window(route: str) -> None:
    source = build_returns_series_response(
        portfolio_returns=_RETURNS,
        as_of_date="2026-01-06",
        resolved_start_date="2025-12-31",
    )

    response = _post(route, source)

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_INVALID_RESPONSE"
    assert error["details"]["field"] == "resolved_window"


@pytest.mark.parametrize(
    "route",
    ["/analytics/risk/calculate", "/analytics/risk/rolling-metrics"],
)
def test_stateful_routes_refuse_return_rows_outside_resolved_window(route: str) -> None:
    source = build_returns_series_response(
        portfolio_returns=(("2025-12-31", "0.0100"), *_RETURNS),
        as_of_date="2026-01-06",
        resolved_start_date="2026-01-01",
    )

    response = _post(route, source)

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_INVALID_RESPONSE"
    assert error["details"]["field"] == "series.portfolio_returns.date"


@pytest.mark.parametrize(
    "route",
    ["/analytics/risk/calculate", "/analytics/risk/rolling-metrics"],
)
def test_stateful_routes_refuse_absent_source_qualification(route: str) -> None:
    source = build_returns_series_response(
        portfolio_returns=_RETURNS,
        as_of_date="2026-01-06",
        resolved_start_date="2026-01-01",
    )
    source.pop("diagnostics")

    response = _post(route, source)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_INVALID_RESPONSE"


@pytest.mark.parametrize(
    "route",
    ["/analytics/risk/calculate", "/analytics/risk/rolling-metrics"],
)
def test_changed_producer_identity_does_not_change_request_fingerprint(route: str) -> None:
    first = build_returns_series_response(
        portfolio_returns=_RETURNS,
        as_of_date="2026-01-06",
        resolved_start_date="2026-01-01",
    )
    second = deepcopy(first)
    second["calculation_id"] = "00000000-0000-4000-8000-000000000002"
    second["provenance"]["input_fingerprint"] = "sha256:" + "3" * 64

    first_response = _post(route, first)
    second_response = _post(route, second)

    assert first_response.status_code == second_response.status_code == 200
    first_metadata = first_response.json()["metadata"]
    second_metadata = second_response.json()["metadata"]
    assert first_metadata["request_fingerprint"] == second_metadata["request_fingerprint"]
    assert (
        first_metadata["source_returns_evidence"]["calculation_id"]
        != second_metadata["source_returns_evidence"]["calculation_id"]
    )
    assert (
        first_metadata["source_returns_evidence"]["input_fingerprint"]
        != second_metadata["source_returns_evidence"]["input_fingerprint"]
    )
