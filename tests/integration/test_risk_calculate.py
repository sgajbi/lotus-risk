from fastapi.testclient import TestClient

from app.main import app


def _request_payload() -> dict[str, object]:
    return {
        "scope": {"asOfDate": "2025-03-31", "netOrGross": "NET"},
        "portfolioOpenDate": "2024-01-01",
        "periods": [
            {"type": "EXPLICIT", "name": "Explicit", "from": "2025-01-01", "to": "2025-03-31"}
        ],
        "metrics": ["VOLATILITY", "SHARPE", "VAR"],
        "options": {
            "frequency": "DAILY",
            "riskFreeMode": "ANNUAL_RATE",
            "riskFreeAnnualRate": 0.01,
            "var": {
                "method": "HISTORICAL",
                "confidence": 0.95,
                "horizonDays": 1,
                "includeExpectedShortfall": True,
            },
        },
        "returns": [
            {"date": "2025-01-02", "value": 1.0},
            {"date": "2025-01-03", "value": 2.0},
            {"date": "2025-01-06", "value": -1.0},
            {"date": "2025-01-07", "value": 0.5},
        ],
    }


def test_risk_calculate_endpoint_happy_path_alias_contract() -> None:
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
    response = client.post("/analytics/risk/calculate", json=payload)
    assert response.status_code == 422


def test_risk_calculate_benchmark_requirement_behavior() -> None:
    client = TestClient(app)
    payload = _request_payload()
    payload["metrics"] = ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"]
    payload["benchmarkReturns"] = []
    response = client.post("/analytics/risk/calculate", json=payload)
    assert response.status_code == 200
    metrics = response.json()["results"]["Explicit"]["metrics"]
    assert metrics["BETA"]["value"] is None
    assert "Benchmark returns required" in metrics["BETA"]["details"]["error"]


def test_metrics_endpoint_exposes_risk_metric_observability() -> None:
    client = TestClient(app)
    client.post("/analytics/risk/calculate", json=_request_payload())
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    text = metrics_response.text
    assert "risk_metric_requested_total" in text
    assert "risk_metric_duration_seconds" in text
