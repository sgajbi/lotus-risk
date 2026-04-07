from typing import Any, cast

from fastapi.testclient import TestClient

from app.main import app
from tests.support.returns_series_payloads import (
    JAN_2026_PORTFOLIO_RETURNS,
    JAN_2026_RISK_FREE_RETURNS,
    JAN_2026_ROLLING_BENCHMARK_RETURNS,
    build_returns_series_response,
)


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
        return build_returns_series_response(
            portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
            benchmark_returns=JAN_2026_ROLLING_BENCHMARK_RETURNS,
            risk_free_returns=JAN_2026_RISK_FREE_RETURNS,
        )


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
        return build_returns_series_response(
            portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
            benchmark_returns=JAN_2026_ROLLING_BENCHMARK_RETURNS,
        )


class _AutoWiredLotusCoreClient:
    calls: list[dict[str, object]] = []

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        _AutoWiredLotusCoreClient.calls.append(
            {
                "portfolio_id": portfolio_id,
                "request_payload": request_payload,
                "correlation_id": correlation_id,
            }
        )
        return {
            "valuation_context": {
                "portfolio_currency": "USD",
                "reporting_currency": "USD",
            }
        }


def _stateless_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-08", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-03", "value": -2.0},
                {"date": "2026-01-04", "value": 0.5},
                {"date": "2026-01-05", "value": 1.2},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-03", "value": -1.5},
                {"date": "2026-01-04", "value": 0.4},
                {"date": "2026-01-05", "value": 1.0},
            ],
            "risk_free_returns": [
                {"date": "2026-01-02", "value": 0.01},
                {"date": "2026-01-03", "value": 0.01},
                {"date": "2026-01-04", "value": 0.01},
                {"date": "2026-01-05", "value": 0.01},
            ],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": [
                    "ROLLING_VOLATILITY",
                    "ROLLING_SHARPE",
                    "ROLLING_BETA",
                    "ROLLING_TRACKING_ERROR",
                    "ROLLING_INFORMATION_RATIO",
                    "ROLLING_MAX_DRAWDOWN",
                ],
                "include_time_series": True,
            },
        },
    }


def test_rolling_metrics_endpoint_stateless_contract() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/rolling-metrics", json=_stateless_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source_service"] == "lotus-risk"
    assert body["input_mode"] == "stateless"
    assert body["metadata"]["methodology_version"] == "rolling_metrics.v1"
    assert "YTD" in body["results"]
    window = body["results"]["YTD"]["window_results"][0]
    assert window["window_length"] == 3
    assert "ROLLING_VOLATILITY" in window["metric_summaries"]


def test_rolling_metrics_endpoint_stateful_uses_lotus_performance() -> None:
    recorder = _RecordingLotusPerformanceClient()
    app.state.lotus_performance_client = recorder
    app.state.lotus_core_client = _AutoWiredLotusCoreClient()
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/rolling-metrics",
        headers={"X-Correlation-Id": "corr-rolling-stateful"},
        json={
            "input_mode": "stateful",
            "stateful_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-04",
                "periods": [{"type": "YTD", "name": "YTD"}],
                "rolling_options": {
                    "window_lengths": [2],
                    "metrics": [
                        "ROLLING_VOLATILITY",
                        "ROLLING_SHARPE",
                        "ROLLING_BETA",
                    ],
                },
            },
        },
    )
    assert response.status_code == 200
    assert len(recorder.calls) == 1
    assert recorder.calls[0]["correlation_id"] == "corr-rolling-stateful"
    payload = recorder.calls[0]["request_payload"]
    assert isinstance(payload, dict)
    assert payload["input_mode"] == "stateful"
    assert payload["stateful_input"] == {}
    assert payload["reporting_currency"] == "USD"
    assert payload["series_selection"]["include_benchmark"] is True
    assert payload["series_selection"]["include_risk_free"] is True
    assert response.json()["input_mode"] == "stateful"


def test_rolling_metrics_endpoint_stateful_autowires_performance_client() -> None:
    import app.main as main_module

    main_module_any = cast(Any, main_module)
    original = main_module_any.LotusPerformanceClient
    original_core = main_module_any.LotusCoreClient
    try:
        main_module_any.LotusPerformanceClient = _AutoWiredLotusPerformanceClient
        main_module_any.LotusCoreClient = _AutoWiredLotusCoreClient
        app.state.lotus_performance_client = None
        app.state.lotus_core_client = None
        _AutoWiredLotusPerformanceClient.calls = []
        _AutoWiredLotusCoreClient.calls = []
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/rolling-metrics",
            headers={"X-Correlation-Id": "corr-rolling-auto"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-04",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "rolling_options": {
                        "window_lengths": [2],
                        "metrics": ["ROLLING_VOLATILITY", "ROLLING_BETA"],
                    },
                },
            },
        )
        assert response.status_code == 200
        assert _AutoWiredLotusPerformanceClient.calls[0]["correlation_id"] == "corr-rolling-auto"
    finally:
        main_module_any.LotusPerformanceClient = original
        main_module_any.LotusCoreClient = original_core


def test_rolling_metrics_endpoint_rejects_simulation_mode_for_now() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/rolling-metrics",
        json={
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-08",
                "periods": [{"type": "YTD"}],
            },
        },
    )
    assert response.status_code == 400
    assert "not implemented" in response.json()["error"]["message"]

