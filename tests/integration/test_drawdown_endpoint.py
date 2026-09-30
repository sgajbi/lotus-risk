from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.observability_contracts import RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS
from tests.support.app_runtime import override_app_runtime
from tests.support.lotus_performance_fakes import (
    RecordingLotusPerformanceClient,
    build_autowired_lotus_performance_client_class,
)
from tests.support.returns_series_payloads import (
    JAN_2026_DRAWDOWN_BENCHMARK_RETURNS,
    JAN_2026_PORTFOLIO_RETURNS,
    build_returns_series_response,
)

_AutoWiredLotusPerformanceClient = build_autowired_lotus_performance_client_class(
    response_factory=lambda: build_returns_series_response(
        portfolio_returns=JAN_2026_PORTFOLIO_RETURNS[:2],
    )
)
_EXPECTED_SUPPORTABILITY_METRIC_LABELS = list(RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS)


def _stateless_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-05", "value": -2.0},
                {"date": "2026-01-06", "value": 0.5},
            ],
        },
        "analysis_options": {"include_underwater_series": True},
    }


def test_drawdown_endpoint_stateless_contract() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/drawdown", json=_stateless_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source_service"] == "lotus-risk"
    assert body["input_mode"] == "stateless"
    assert "YTD" in body["results"]
    assert body["results"]["YTD"]["summary"]["max_drawdown"] is not None
    assert body["results"]["YTD"]["underwater_series"] is not None
    assert body["metadata"]["include_underwater_series"] is True
    assert body["metadata"]["include_episode_list"] is True
    assert body["metadata"]["include_benchmark"] is False
    assert body["metadata"]["missing_benchmark_policy"] == "IGNORE"
    assert body["metadata"]["calculation_supportability"] == {
        "state": "ready",
        "reason": "calculation_complete",
        "freshness_bucket": "current",
        "metric_labels": _EXPECTED_SUPPORTABILITY_METRIC_LABELS,
        "degraded_metric_count": 0,
        "empty_period_count": 0,
        "evaluated_period_count": 1,
    }


def test_drawdown_endpoint_retains_initial_loss_and_undated_opening_peak() -> None:
    payload = _stateless_payload()
    stateless_input = payload["stateless_input"]
    assert isinstance(stateless_input, dict)
    stateless_input["scope"] = {"as_of_date": "2026-01-05", "net_or_gross": "NET"}
    stateless_input["returns"] = [
        {"date": "2026-01-02", "value": -10.0},
        {"date": "2026-01-05", "value": 0.0},
    ]
    stateless_input["benchmark_returns"] = [
        {"date": "2026-01-02", "value": 0.0},
        {"date": "2026-01-05", "value": 0.0},
    ]
    payload["benchmark_policy"] = {
        "include_benchmark": True,
        "missing_benchmark_policy": "REQUIRE",
    }

    response = TestClient(app).post("/analytics/risk/drawdown", json=payload)

    assert response.status_code == 200
    period = response.json()["results"]["YTD"]
    summary = period["summary"]
    assert summary["max_drawdown"] == pytest.approx(-0.1)
    assert summary["max_drawdown_peak_date"] is None
    assert summary["max_drawdown_trough_date"] == "2026-01-02"
    assert summary["is_recovered"] is False
    assert summary["days_to_trough"] is None
    assert summary["time_under_water_days"] == 2
    assert [point["drawdown"] for point in period["underwater_series"]] == pytest.approx(
        [-0.1, -0.1]
    )
    assert period["episodes"][0]["peak_date"] is None
    assert period["episodes"][0]["total_days"] is None
    assert period["relative_to_benchmark"]["max_drawdown"] == pytest.approx(-0.1)
    assert period["relative_to_benchmark"]["max_drawdown_peak_date"] is None


def test_drawdown_endpoint_preserves_negative_equity_instead_of_zeroing_loss() -> None:
    payload = _stateless_payload()
    stateless_input = payload["stateless_input"]
    assert isinstance(stateless_input, dict)
    stateless_input["scope"] = {"as_of_date": "2026-01-05", "net_or_gross": "NET"}
    stateless_input["returns"] = [
        {"date": "2026-01-02", "value": -101.0},
        {"date": "2026-01-05", "value": 0.0},
    ]

    response = TestClient(app).post("/analytics/risk/drawdown", json=payload)

    assert response.status_code == 200
    period = response.json()["results"]["YTD"]
    assert period["summary"]["max_drawdown"] == pytest.approx(-1.01)
    assert period["summary"]["is_recovered"] is False
    assert [point["drawdown"] for point in period["underwater_series"]] == pytest.approx(
        [-1.01, -1.01]
    )


def test_drawdown_endpoint_stateful_uses_lotus_performance() -> None:
    recorder = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
            benchmark_returns=JAN_2026_DRAWDOWN_BENCHMARK_RETURNS,
        )
    )
    with override_app_runtime(lotus_performance_client=recorder):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/drawdown",
            headers={"X-Correlation-Id": "corr-dd-stateful", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "benchmark_policy": {
                        "include_benchmark": True,
                        "missing_benchmark_policy": "REQUIRE",
                    },
                },
                "analysis_options": {"top_n_episodes": 3},
            },
        )
    assert response.status_code == 200
    assert len(recorder.calls) == 1
    assert recorder.calls[0]["correlation_id"] == "corr-dd-stateful"
    payload = recorder.calls[0]["request_payload"]
    assert isinstance(payload, dict)
    assert payload["input_mode"] == "stateful"
    assert payload["stateful_input"] == {}
    assert payload["benchmark"] == {
        "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
        "return_source": "calculated",
    }
    assert payload["series_selection"]["include_benchmark"] is True
    body = response.json()
    assert body["input_mode"] == "stateful"
    assert body["results"]["YTD"]["portfolio_observation_count"] == len(JAN_2026_PORTFOLIO_RETURNS)
    assert body["results"]["YTD"]["benchmark_observation_count"] == len(
        JAN_2026_DRAWDOWN_BENCHMARK_RETURNS
    )
    assert body["metadata"]["include_benchmark"] is True
    assert body["metadata"]["missing_benchmark_policy"] == "REQUIRE"
    assert body["metadata"]["top_n_episodes"] == 3
    assert body["results"]["YTD"]["relative_to_benchmark_context"]["requested"] is True
    assert body["results"]["YTD"]["relative_to_benchmark_context"]["applied"] is True
    assert body["results"]["YTD"]["relative_to_benchmark_context"]["reason"] == "APPLIED"
    assert body["results"]["YTD"]["relative_to_benchmark"]["time_under_water_days"] >= 0
    assert body["metadata"]["source_returns_evidence"] == {
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


def test_drawdown_endpoint_stateful_preserves_stale_producer_qualification() -> None:
    recorder = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
            freshness="stale",
        )
    )
    with override_app_runtime(lotus_performance_client=recorder):
        response = TestClient(app).post(
            "/analytics/risk/drawdown",
            headers={"X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD"}],
                },
            },
        )

    assert response.status_code == 200
    supportability = response.json()["metadata"]["calculation_supportability"]
    assert supportability["state"] == "stale"
    assert supportability["reason"] == "stale_source_observations"
    assert supportability["freshness_bucket"] == "stale"
    assert response.json()["metadata"]["source_returns_evidence"]["freshness"] == "stale"


def test_drawdown_endpoint_stateful_preserves_partial_producer_qualification() -> None:
    recorder = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=JAN_2026_PORTFOLIO_RETURNS[:2],
            as_of_date="2026-01-06",
            requested_points=3,
            returned_points=2,
            missing_points=1,
        )
    )
    with override_app_runtime(lotus_performance_client=recorder):
        response = TestClient(app).post(
            "/analytics/risk/drawdown",
            headers={"X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD"}],
                },
            },
        )

    assert response.status_code == 200
    supportability = response.json()["metadata"]["calculation_supportability"]
    assert supportability["state"] == "degraded"
    assert supportability["reason"] == "calculation_quality_issue"
    assert supportability["degraded_metric_count"] == 0
    assert response.json()["metadata"]["source_returns_evidence"]["missing_points"] == 1


def test_drawdown_endpoint_stateful_rejects_missing_source_qualification() -> None:
    recorder = RecordingLotusPerformanceClient(
        response_payload={
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "0.01"},
                ]
            }
        }
    )
    with override_app_runtime(lotus_performance_client=recorder):
        response = TestClient(app).post(
            "/analytics/risk/drawdown",
            headers={"X-Tenant-Id": "tenant-a", "X-Correlation-Id": "corr-source-missing"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD"}],
                },
            },
        )

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_INVALID_RESPONSE"
    assert error["details"]["field"] == "source_qualification"
    assert error["correlation_id"] == "corr-source-missing"


def test_drawdown_endpoint_maps_malformed_upstream_return_dates_to_502() -> None:
    recorder = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=(("not-a-date", "0.0100"),),
        )
    )
    with override_app_runtime(lotus_performance_client=recorder):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/drawdown",
            headers={"X-Correlation-Id": "corr-dd-bad-date", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                },
            },
        )

    body = response.json()["error"]
    assert response.status_code == 502
    assert body["code"] == "UPSTREAM_INVALID_RESPONSE"
    assert body["message"] == "Upstream dependency returned an invalid response."
    assert body["details"]["category"] == "invalid_response"
    assert body["details"]["retryable"] is False
    assert body["correlation_id"] == "corr-dd-bad-date"


def test_drawdown_endpoint_marks_benchmark_unavailable_when_requested_without_series() -> None:
    client = TestClient(app)
    payload = _stateless_payload()
    payload["stateless_input"]["benchmark_returns"] = []  # type: ignore[index]
    payload["benchmark_policy"] = {
        "include_benchmark": True,
        "missing_benchmark_policy": "REQUIRE",
    }
    response = client.post("/analytics/risk/drawdown", json=payload)
    assert response.status_code == 200
    period = response.json()["results"]["YTD"]
    assert period["benchmark_observation_count"] == 0
    assert period["relative_to_benchmark"] is None
    assert period["relative_to_benchmark_context"] == {
        "requested": True,
        "applied": False,
        "reason": "BENCHMARK_UNAVAILABLE",
        "aligned_observation_count": 0,
    }
    assert response.json()["metadata"]["calculation_supportability"] == {
        "state": "degraded",
        "reason": "benchmark_unavailable",
        "freshness_bucket": "current",
        "metric_labels": _EXPECTED_SUPPORTABILITY_METRIC_LABELS,
        "degraded_metric_count": 1,
        "empty_period_count": 0,
        "evaluated_period_count": 1,
    }


def test_drawdown_endpoint_supportability_marks_empty_periods() -> None:
    client = TestClient(app)
    payload = _stateless_payload()
    payload["stateless_input"]["periods"] = [  # type: ignore[index]
        {
            "type": "EXPLICIT",
            "name": "EMPTY",
            "from_date": "2025-12-01",
            "to_date": "2025-12-31",
        }
    ]
    response = client.post("/analytics/risk/drawdown", json=payload)
    assert response.status_code == 200
    assert response.json()["metadata"]["calculation_supportability"] == {
        "state": "degraded",
        "reason": "insufficient_observations",
        "freshness_bucket": "current",
        "metric_labels": _EXPECTED_SUPPORTABILITY_METRIC_LABELS,
        "degraded_metric_count": 1,
        "empty_period_count": 1,
        "evaluated_period_count": 1,
    }


def test_drawdown_endpoint_marks_no_aligned_benchmark_observations() -> None:
    client = TestClient(app)
    payload = _stateless_payload()
    payload["stateless_input"]["benchmark_returns"] = [  # type: ignore[index]
        {"date": "2025-12-29", "value": 0.5},
        {"date": "2025-12-30", "value": -0.1},
    ]
    payload["benchmark_policy"] = {
        "include_benchmark": True,
        "missing_benchmark_policy": "REQUIRE",
    }
    response = client.post("/analytics/risk/drawdown", json=payload)
    assert response.status_code == 200
    period = response.json()["results"]["YTD"]
    assert period["benchmark_observation_count"] == 0
    assert period["relative_to_benchmark"] is None
    assert period["relative_to_benchmark_context"] == {
        "requested": True,
        "applied": False,
        "reason": "NO_ALIGNED_OBSERVATIONS",
        "aligned_observation_count": 0,
    }


def test_drawdown_endpoint_rejects_simulation_mode_at_contract_boundary() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/drawdown",
        json={
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-06",
                "periods": [{"type": "YTD"}],
            },
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_drawdown_endpoint_stateful_uses_runtime_performance_client_override() -> None:
    _AutoWiredLotusPerformanceClient.calls = []
    with override_app_runtime(
        lotus_performance_client=_AutoWiredLotusPerformanceClient(),
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/drawdown",
            headers={"X-Correlation-Id": "corr-dd-runtime", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-05",
                    "periods": [{"type": "YTD"}],
                },
            },
        )
        assert response.status_code == 200
        assert _AutoWiredLotusPerformanceClient.calls[0]["correlation_id"] == "corr-dd-runtime"
