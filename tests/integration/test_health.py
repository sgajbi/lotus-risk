from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoints() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert client.get("/ops").status_code == 200


def test_correlation_header_propagation() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Correlation-Id": "corr-123"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-123"


def test_integration_capabilities_contract() -> None:
    client = TestClient(app)
    response = client.get("/integration/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["sourceService"] == "lotus-risk"
    assert body["policyVersion"] == "risk.v1"
    assert body["supportedInputModes"] == ["stateless", "stateful", "simulation"]
    assert isinstance(body["features"], list)
    assert isinstance(body["workflows"], list)
    feature_keys = {feature["key"] for feature in body["features"]}
    assert feature_keys == {
        "risk.analytics.risk_analytics",
        "risk.analytics.concentration",
        "risk.analytics.metrics",
    }
    workflow_keys = {workflow["workflow_key"] for workflow in body["workflows"]}
    assert workflow_keys == {"risk_snapshot", "concentration_risk"}


def _concentration_payload() -> dict[str, object]:
    return {
        "currentPositions": [
            {"securityId": "A", "quantity": 10},
            {"securityId": "B", "quantity": 10},
        ],
        "projectedPositions": [
            {"securityId": "A", "proposedQuantity": 15},
            {"securityId": "B", "proposedQuantity": 5},
        ],
    }


def test_concentration_risk_endpoint() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/concentration", json=_concentration_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["sourceService"] == "lotus-risk"
    assert "riskProxy" in body
    assert body["riskProxy"]["hhiCurrent"] > 0


def test_legacy_workbench_proxy_is_not_exposed() -> None:
    client = TestClient(app)
    response = client.post("/analytics/workbench/risk-proxy", json=_concentration_payload())
    assert response.status_code == 404
    body = response.json()["error"]
    assert body["code"] == "RESOURCE_NOT_FOUND"


def test_concentration_handles_non_positive_positions() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/concentration",
        json={
            "currentPositions": [{"securityId": "A", "quantity": 0}],
            "projectedPositions": [{"securityId": "B", "proposedQuantity": -5}],
        },
    )
    assert response.status_code == 200
    proxy = response.json()["riskProxy"]
    assert proxy["hhiCurrent"] == 0
    assert proxy["hhiProposed"] == 0
    assert proxy["hhiDelta"] == 0


def test_openapi_hides_legacy_proxy_and_exposes_concentration() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    assert "/analytics/risk/concentration" in spec["paths"]
    assert "/ops" in spec["paths"]
    assert "/analytics/workbench/risk-proxy" not in spec["paths"]


def test_metadata_and_ops_contract_shape() -> None:
    client = TestClient(app)
    metadata = client.get("/metadata")
    ops = client.get("/ops")
    assert metadata.status_code == 200
    assert ops.status_code == 200
    metadata_body = metadata.json()
    ops_body = ops.json()
    assert metadata_body["service"] == "lotus-risk"
    assert metadata_body["version"] == "0.1.0"
    assert "roundingPolicyVersion" in metadata_body
    assert ops_body["status"] == "ok"
    assert ops_body["checks"]["live"] is True
    assert ops_body["checks"]["ready"] is True
    assert ops_body["checks"]["draining"] is False
    assert ops_body["inputModes"] == ["stateless", "stateful", "simulation"]


def test_openapi_exposes_typed_capabilities_response_contract() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    capabilities_get = spec["paths"]["/integration/capabilities"]["get"]
    schema_ref = capabilities_get["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ]
    assert schema_ref.endswith("/IntegrationCapabilitiesResponse")
