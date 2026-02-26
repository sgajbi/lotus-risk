from fastapi.testclient import TestClient
from src.app.main import app


def test_health_endpoints() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_correlation_header_propagation() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Correlation-Id": "corr-123"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-123"


def test_integration_capabilities_contract() -> None:
    client = TestClient(app)
    response = client.get('/integration/capabilities')
    assert response.status_code == 200
    body = response.json()
    assert body['sourceService'] == 'lotus-risk'
    assert isinstance(body['features'], list)
    assert isinstance(body['workflows'], list)


def test_workbench_risk_proxy_endpoint() -> None:
    client = TestClient(app)
    response = client.post(
        '/analytics/workbench/risk-proxy',
        json={
            'currentPositions': [
                {'securityId': 'A', 'quantity': 10},
                {'securityId': 'B', 'quantity': 10},
            ],
            'projectedPositions': [
                {'securityId': 'A', 'proposedQuantity': 15},
                {'securityId': 'B', 'proposedQuantity': 5},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body['sourceService'] == 'lotus-risk'
    assert 'riskProxy' in body
    assert body['riskProxy']['hhiCurrent'] > 0

