from fastapi.testclient import TestClient

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
            headers={"X-Correlation-Id": "corr-dd-stateful"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
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


def test_drawdown_endpoint_stateful_autowires_performance_client() -> None:
    with override_app_runtime(
        lotus_performance_client=None,
        lotus_performance_class=_AutoWiredLotusPerformanceClient,
    ):
        _AutoWiredLotusPerformanceClient.calls = []
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/drawdown",
            headers={"X-Correlation-Id": "corr-dd-auto"},
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
        assert _AutoWiredLotusPerformanceClient.calls[0]["correlation_id"] == "corr-dd-auto"
