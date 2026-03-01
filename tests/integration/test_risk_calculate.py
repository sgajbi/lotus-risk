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
                    {"date": "2025-01-02", "return_value": "0.0100"},
                    {"date": "2025-01-03", "return_value": "0.0200"},
                    {"date": "2025-01-06", "return_value": "-0.0100"},
                    {"date": "2025-01-07", "return_value": "0.0050"},
                ],
                "benchmark_returns": [
                    {"date": "2025-01-02", "return_value": "0.0090"},
                    {"date": "2025-01-03", "return_value": "0.0150"},
                    {"date": "2025-01-06", "return_value": "-0.0080"},
                    {"date": "2025-01-07", "return_value": "0.0040"},
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
                    {"date": "2025-01-02", "return_value": "0.0100"},
                    {"date": "2025-01-03", "return_value": "0.0200"},
                ]
            }
        }


def _request_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
            "portfolio_open_date": "2024-01-01",
            "periods": [
                {
                    "type": "EXPLICIT",
                    "name": "Explicit",
                    "from_date": "2025-01-01",
                    "to_date": "2025-03-31",
                }
            ],
            "metrics": ["VOLATILITY", "SHARPE", "VAR"],
            "options": {
                "frequency": "DAILY",
                "risk_free_mode": "ANNUAL_RATE",
                "risk_free_annual_rate": 0.01,
                "var": {
                    "method": "HISTORICAL",
                    "confidence": 0.95,
                    "horizon_days": 1,
                    "include_expected_shortfall": True,
                },
            },
            "returns": [
                {"date": "2025-01-02", "value": 1.0},
                {"date": "2025-01-03", "value": 2.0},
                {"date": "2025-01-06", "value": -1.0},
                {"date": "2025-01-07", "value": 0.5},
            ],
        },
    }


def test_risk_calculate_endpoint_happy_path_contract() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/calculate", json=_request_payload())
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert "Explicit" in body["results"]
    metrics = body["results"]["Explicit"]["metrics"]
    assert metrics["VOLATILITY"]["value"] is not None
    assert metrics["SHARPE"]["value"] is not None
    assert metrics["VAR"]["value"] is not None


def test_risk_calculate_endpoint_rejects_invalid_explicit_period() -> None:
    client = TestClient(app)
    payload = _request_payload()
    payload["periods"] = [{"type": "EXPLICIT", "name": "Bad"}]
    response = client.post(
        "/analytics/risk/calculate",
        json=payload,
        headers={"X-Correlation-Id": "corr-422"},
    )
    assert response.status_code == 422
    assert response.headers["X-Correlation-Id"] == "corr-422"
    body = response.json()["error"]
    assert body["code"] == "INVALID_REQUEST"
    assert body["correlation_id"] == "corr-422"
    assert body["message"] == "Request validation failed"


def test_risk_calculate_benchmark_requirement_behavior() -> None:
    client = TestClient(app)
    payload = _request_payload()
    stateless_input = payload["stateless_input"]
    assert isinstance(stateless_input, dict)
    stateless_input["metrics"] = ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"]
    stateless_input["benchmark_returns"] = []
    response = client.post("/analytics/risk/calculate", json=payload)
    assert response.status_code == 200
    metrics = response.json()["results"]["Explicit"]["metrics"]
    assert metrics["BETA"]["value"] is None
    assert "Benchmark returns required" in metrics["BETA"]["details"]["error"]


def test_risk_calculate_stateful_mode_uses_lotus_performance_returns_series() -> None:
    performance_client = _RecordingLotusPerformanceClient()
    app.state.lotus_performance_client = performance_client
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/calculate",
        headers={"X-Correlation-Id": "corr-risk-stateful"},
        json={
            "input_mode": "stateful",
            "stateful_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2025-01-07",
                "net_or_gross": "NET",
                "periods": [{"type": "YTD", "name": "YTD"}],
                "metrics": ["VOLATILITY", "BETA"],
            },
        },
    )
    assert response.status_code == 200
    payload = performance_client.calls[0]["request_payload"]
    assert isinstance(payload, dict)
    assert payload["portfolio_id"] == "DEMO_DPM_EUR_001"
    assert payload["input_mode"] == "stateful"
    assert payload["stateful_input"] == {"consumer_system": "lotus-risk"}
    assert payload["window"] == {"mode": "RELATIVE", "period": "SI"}
    assert payload["series_selection"] == {
        "include_portfolio": True,
        "include_benchmark": True,
        "include_risk_free": False,
    }
    assert performance_client.calls[0]["correlation_id"] == "corr-risk-stateful"
    metrics = response.json()["results"]["YTD"]["metrics"]
    assert metrics["VOLATILITY"]["value"] is not None
    assert metrics["BETA"]["value"] is not None


def test_risk_calculate_stateful_mode_autowires_lotus_performance_client() -> None:
    import app.main as main_module

    main_module_any = cast(Any, main_module)
    original_client = main_module_any.LotusPerformanceClient
    try:
        main_module_any.LotusPerformanceClient = _AutoWiredLotusPerformanceClient
        app.state.lotus_performance_client = None
        _AutoWiredLotusPerformanceClient.calls = []
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/calculate",
            headers={"X-Correlation-Id": "corr-autowire"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2025-01-03",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "metrics": ["VOLATILITY"],
                },
            },
        )
        assert response.status_code == 200
        assert _AutoWiredLotusPerformanceClient.calls[0]["correlation_id"] == "corr-autowire"
    finally:
        main_module_any.LotusPerformanceClient = original_client


def test_risk_calculate_simulation_mode_returns_not_implemented_error() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/calculate",
        json={
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "periods": [{"type": "YTD", "name": "YTD"}],
                "metrics": ["VOLATILITY"],
            },
        },
    )
    assert response.status_code == 400
    assert "not implemented" in response.json()["error"]["message"]


def test_metrics_endpoint_exposes_risk_metric_observability() -> None:
    client = TestClient(app)
    client.post("/analytics/risk/calculate", json=_request_payload())
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    text = metrics_response.text
    assert "risk_metric_requested_total" in text
    assert "risk_metric_duration_seconds" in text
