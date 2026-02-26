from fastapi.testclient import TestClient

from src.app.main import app


def _request_payload() -> dict:
    return {
        "scope": {"asOfDate": "2025-03-31", "netOrGross": "NET"},
        "portfolioOpenDate": "2024-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "metrics": ["VOLATILITY", "SHARPE", "VAR"],
        "options": {
            "frequency": "DAILY",
            "riskFreeMode": "ANNUAL_RATE",
            "riskFreeAnnualRate": 0.01,
            "var": {"confidence": 0.95, "horizonDays": 1, "includeExpectedShortfall": True},
        },
        "returns": [
            {"date": "2025-01-02", "value": 1.0},
            {"date": "2025-01-03", "value": 2.0},
            {"date": "2025-01-06", "value": -1.0},
            {"date": "2025-01-07", "value": 0.5},
        ],
    }


def test_risk_calculate_endpoint_happy_path() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/calculate", json=_request_payload())
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert "YTD" in body["results"]
    metrics = body["results"]["YTD"]["metrics"]
    assert metrics["VOLATILITY"]["value"] is not None
    assert metrics["SHARPE"]["value"] is not None
    assert metrics["VAR"]["value"] is not None


def test_risk_calculate_endpoint_rejects_invalid_custom_period() -> None:
    client = TestClient(app)
    payload = _request_payload()
    payload["periods"] = [{"type": "CUSTOM", "name": "Custom"}]
    response = client.post("/analytics/risk/calculate", json=payload)
    assert response.status_code == 400
    assert "CUSTOM period requires" in response.json()["detail"]
