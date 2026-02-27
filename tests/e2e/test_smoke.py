from fastapi.testclient import TestClient
from app.main import app


def _risk_payload() -> dict[str, object]:
    return {
        "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
        "portfolio_open_date": "2024-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "metrics": ["VOLATILITY", "VAR"],
        "returns": [
            {"date": "2025-01-02", "value": 0.8},
            {"date": "2025-01-03", "value": -0.2},
            {"date": "2025-01-06", "value": 0.3},
        ],
    }


def test_e2e_smoke() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metadata_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/metadata")
    assert response.status_code == 200
    assert response.json()["service"].startswith("lotus-")


def test_e2e_risk_calculate_happy_path() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/calculate", json=_risk_payload())
    assert response.status_code == 200
    body = response.json()
    assert "YTD" in body["results"]
    metrics = body["results"]["YTD"]["metrics"]
    assert metrics["VOLATILITY"]["value"] is not None
    assert metrics["VAR"]["value"] is not None


def test_e2e_risk_calculate_invalid_period_contract() -> None:
    client = TestClient(app)
    payload = _risk_payload()
    payload["periods"] = [{"type": "EXPLICIT", "name": "Bad"}]
    response = client.post("/analytics/risk/calculate", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_e2e_concentration_stateless_legacy_payload() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/concentration",
        json={
            "current_positions": [
                {"security_id": "A", "quantity": 10},
                {"security_id": "B", "quantity": 10},
            ],
            "projected_positions": [
                {"security_id": "A", "proposed_quantity": 15},
                {"security_id": "B", "proposed_quantity": 5},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateless"
    assert body["risk_proxy"]["hhi_proposed"] == 6250.0
