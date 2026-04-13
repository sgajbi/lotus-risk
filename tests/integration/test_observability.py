from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.support.app_runtime import override_app_runtime
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import build_returns_series_response


client = TestClient(app)


def _risk_stateless_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-03-31", "net_or_gross": "NET"},
            "portfolio_open_date": "2026-01-02",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY"],
            "returns": [
                {"date": "2026-01-02", "value": 0.5},
                {"date": "2026-01-05", "value": -0.2},
            ],
        },
    }


def _risk_stateful_payload() -> dict[str, object]:
    return {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-03-31",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY"],
        },
    }


def test_metrics_expose_endpoint_execution_mode_and_outcome() -> None:
    response = client.post("/analytics/risk/calculate", json=_risk_stateless_payload())
    assert response.status_code == 200

    metrics = client.get("/metrics").text

    assert 'lotus_risk_endpoint_executions_total{endpoint="risk/calculate"' in metrics
    assert 'input_mode="stateless"' in metrics
    assert 'outcome="success"' in metrics
    assert "lotus_risk_endpoint_execution_seconds_bucket" in metrics


def test_metrics_expose_stateful_endpoint_execution_mode() -> None:
    performance_client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=[
                ("2026-01-02", "0.005"),
                ("2026-01-05", "-0.002"),
            ]
        )
    )

    with override_app_runtime(lotus_performance_client=performance_client):
        response = client.post(
            "/analytics/risk/calculate",
            json=_risk_stateful_payload(),
            headers={"X-Correlation-Id": "corr-observability"},
        )

    assert response.status_code == 200
    metrics = client.get("/metrics").text

    assert 'input_mode="stateful"' in metrics
