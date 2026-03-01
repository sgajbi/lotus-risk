from fastapi.testclient import TestClient
from typing import Any, cast

from app.main import app


class _RecordingLotusPerformanceClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "request_payload": request_payload,
                "correlation_id": correlation_id,
            }
        )
        return {
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "0.0100"},
                    {"date": "2026-01-03", "return_value": "-0.0200"},
                    {"date": "2026-01-04", "return_value": "0.0050"},
                ],
                "benchmark_returns": [
                    {"date": "2026-01-02", "return_value": "0.0070"},
                    {"date": "2026-01-03", "return_value": "-0.0100"},
                    {"date": "2026-01-04", "return_value": "0.0040"},
                ],
            }
        }


class _AutoWiredLotusPerformanceClient:
    calls: list[dict[str, object]] = []

    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        _AutoWiredLotusPerformanceClient.calls.append(
            {
                "request_payload": request_payload,
                "correlation_id": correlation_id,
            }
        )
        return {
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "0.0100"},
                    {"date": "2026-01-03", "return_value": "-0.0200"},
                ]
            }
        }


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


def test_drawdown_endpoint_stateful_uses_lotus_performance() -> None:
    recorder = _RecordingLotusPerformanceClient()
    app.state.lotus_performance_client = recorder
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
    assert payload["stateful_input"] == {"consumer_system": "lotus-risk"}
    assert payload["series_selection"]["include_benchmark"] is True
    assert response.json()["input_mode"] == "stateful"


def test_drawdown_endpoint_rejects_simulation_mode_for_now() -> None:
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
    assert response.status_code == 400
    assert "not implemented" in response.json()["error"]["message"]


def test_drawdown_endpoint_stateful_autowires_performance_client() -> None:
    import app.main as main_module

    main_module_any = cast(Any, main_module)
    original = main_module_any.LotusPerformanceClient
    try:
        main_module_any.LotusPerformanceClient = _AutoWiredLotusPerformanceClient
        app.state.lotus_performance_client = None
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
    finally:
        main_module_any.LotusPerformanceClient = original
