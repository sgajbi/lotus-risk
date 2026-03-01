from fastapi.testclient import TestClient

from app.main import app


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


def test_risk_calculate_rejects_non_stateless_modes_in_slice_one() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/calculate",
        json={
            "input_mode": "stateful",
            "stateful_input": {"portfolio_id": "DEMO_DPM_EUR_001", "as_of_date": "2026-02-27"},
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
