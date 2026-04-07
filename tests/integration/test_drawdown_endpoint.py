from fastapi.testclient import TestClient

from app.main import app
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


def _stateless_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-04", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-03", "value": -2.0},
                {"date": "2026-01-04", "value": 0.5},
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
    assert body["metadata"]["include_benchmark"] is None


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
                    "as_of_date": "2026-01-04",
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
    assert body["metadata"]["include_benchmark"] is True
    assert body["metadata"]["missing_benchmark_policy"] == "REQUIRE"
    assert body["metadata"]["top_n_episodes"] == 3


def test_drawdown_endpoint_rejects_simulation_mode_at_contract_boundary() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/drawdown",
        json={
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-04",
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
                    "as_of_date": "2026-01-03",
                    "periods": [{"type": "YTD"}],
                },
            },
        )
        assert response.status_code == 200
        assert _AutoWiredLotusPerformanceClient.calls[0]["correlation_id"] == "corr-dd-auto"
