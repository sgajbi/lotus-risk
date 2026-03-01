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
    assert body["source_service"] == "lotus-risk"
    assert body["policy_version"] == "risk.v1"
    assert body["supported_input_modes"] == ["stateless", "stateful", "simulation"]
    assert isinstance(body["features"], list)
    assert isinstance(body["workflows"], list)
    feature_keys = {feature["key"] for feature in body["features"]}
    assert feature_keys == {
        "risk.analytics.risk_analytics",
        "risk.analytics.concentration",
        "risk.analytics.drawdown",
        "risk.analytics.metrics",
    }
    workflow_keys = {workflow["workflow_key"] for workflow in body["workflows"]}
    assert workflow_keys == {"risk_snapshot", "concentration_risk", "drawdown_analytics"}


def _concentration_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "current_positions": [
                {"security_id": "A", "quantity": 10},
                {"security_id": "B", "quantity": 10},
            ],
            "projected_positions": [
                {"security_id": "A", "proposed_quantity": 15},
                {"security_id": "B", "proposed_quantity": 5},
            ],
        },
    }


def test_concentration_risk_endpoint() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/concentration", json=_concentration_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source_service"] == "lotus-risk"
    assert "risk_proxy" in body
    assert body["risk_proxy"]["hhi_current"] > 0


def test_legacy_workbench_proxy_removed_with_standard_404_error() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/workbench/risk-proxy",
        json=_concentration_payload(),
        headers={"X-Correlation-Id": "corr-legacy-404"},
    )
    assert response.status_code == 404
    assert response.headers["X-Correlation-Id"] == "corr-legacy-404"
    body = response.json()["error"]
    assert body["code"] == "RESOURCE_NOT_FOUND"
    assert body["correlation_id"] == "corr-legacy-404"


def test_concentration_handles_non_positive_positions() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/concentration",
        json={
            "input_mode": "stateless",
            "stateless_input": {
                "current_positions": [{"security_id": "A", "quantity": 0}],
                "projected_positions": [{"security_id": "B", "proposed_quantity": -5}],
            },
        },
    )
    assert response.status_code == 200
    proxy = response.json()["risk_proxy"]
    assert proxy["hhi_current"] == 0
    assert proxy["hhi_proposed"] == 0
    assert proxy["hhi_delta"] == 0


def test_openapi_hides_legacy_proxy_and_exposes_concentration() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    assert "/analytics/risk/concentration" in spec["paths"]
    assert "/analytics/risk/drawdown" in spec["paths"]
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
    assert "rounding_policy_version" in metadata_body
    assert ops_body["status"] == "ok"
    assert ops_body["checks"]["live"] is True
    assert ops_body["checks"]["ready"] is True
    assert ops_body["checks"]["draining"] is False
    assert ops_body["input_modes"] == ["stateless", "stateful", "simulation"]


def test_openapi_declares_standard_error_models_for_risk_endpoints() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    calculate_responses = spec["paths"]["/analytics/risk/calculate"]["post"]["responses"]
    concentration_responses = spec["paths"]["/analytics/risk/concentration"]["post"]["responses"]
    drawdown_responses = spec["paths"]["/analytics/risk/drawdown"]["post"]["responses"]

    for responses in (calculate_responses, concentration_responses, drawdown_responses):
        for status_code in ("400", "403", "404", "422"):
            schema_ref = responses[status_code]["content"]["application/json"]["schema"]["$ref"]
            assert schema_ref.endswith("/ErrorResponse")
        assert responses["400"]["content"]["application/json"]["example"]["error"]["code"] == (
            "INVALID_INPUT"
        )
        assert responses["403"]["content"]["application/json"]["example"]["error"]["code"] == (
            "AUTHORIZATION_DENIED"
        )
        assert responses["404"]["content"]["application/json"]["example"]["error"]["code"] == (
            "RESOURCE_NOT_FOUND"
        )
        assert responses["422"]["content"]["application/json"]["example"]["error"]["code"] == (
            "INVALID_REQUEST"
        )


def test_openapi_exposes_typed_capabilities_response_contract() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    capabilities_get = spec["paths"]["/integration/capabilities"]["get"]
    schema_ref = capabilities_get["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ]
    assert schema_ref.endswith("/IntegrationCapabilitiesResponse")


def test_concentration_rejects_legacy_payload_shape() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/concentration",
        json={
            "current_positions": [{"security_id": "A", "quantity": 10}],
            "projected_positions": [{"security_id": "B", "proposed_quantity": 5}],
        },
    )
    assert response.status_code == 422


class _FakeLotusCoreClient:
    async def create_simulation_session(
        self,
        *,
        portfolio_id: str,
        ttl_hours: int | None,
        created_by: str | None,
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {
            "session": {
                "session_id": "SIM_0001",
                "portfolio_id": portfolio_id,
                "status": "ACTIVE",
                "version": 1,
                "created_by": created_by,
                "created_at": "2026-02-27T10:30:00Z",
                "expires_at": "2026-02-28T10:30:00Z",
            }
        }

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, object]],
        correlation_id: str | None,
    ) -> dict[str, object]:
        assert session_id == "SIM_0001"
        assert len(changes) == 1
        return {"session_id": session_id, "version": 3, "changes": []}

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        if request_payload.get("snapshot_mode") == "BASELINE":
            return {
                "portfolio_id": portfolio_id,
                "as_of_date": "2026-02-27",
                "snapshot_mode": "BASELINE",
                "valuation_context": {
                    "portfolio_currency": "EUR",
                    "reporting_currency": "USD",
                    "position_basis": "market_value_base",
                    "weight_basis": "total_market_value_base",
                },
                "sections": {
                    "positions_baseline": [
                        {"security_id": "SEC_A", "market_value_base": "80"},
                        {"security_id": "SEC_B", "market_value_base": "20"},
                    ]
                },
            }
        return {
            "portfolio_id": portfolio_id,
            "as_of_date": "2026-02-27",
            "snapshot_mode": "SIMULATION",
            "valuation_context": {
                "portfolio_currency": "EUR",
                "reporting_currency": "USD",
                "position_basis": "market_value_base",
                "weight_basis": "total_market_value_base",
            },
            "simulation": {
                "session_id": "SIM_0001",
                "version": 3,
                "baseline_as_of_date": "2026-02-27",
            },
            "sections": {
                "positions_baseline": [
                    {"security_id": "SEC_A", "market_value_base": "60"},
                    {"security_id": "SEC_B", "market_value_base": "40"},
                ],
                "positions_projected": [
                    {"security_id": "SEC_A", "market_value_base": "90"},
                    {"security_id": "SEC_B", "market_value_base": "10"},
                ],
            },
        }

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {
            "records": [
                {"security_id": security_id, "issuer_id": f"ISSUER_{security_id}"}
                for security_id in security_ids
            ]
        }


def test_concentration_stateful_mode_uses_lotus_core_snapshot() -> None:
    client = TestClient(app)
    app.state.lotus_core_client = _FakeLotusCoreClient()
    response = client.post(
        "/analytics/risk/concentration",
        json={
            "input_mode": "stateful",
            "stateful_input": {"portfolio_id": "DEMO_DPM_EUR_001", "as_of_date": "2026-02-27"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateful"
    assert body["risk_proxy"]["hhi_current"] == 6800.0
    assert body["metadata"]["portfolio_id"] == "DEMO_DPM_EUR_001"


def test_concentration_simulation_mode_reuses_or_creates_session_and_returns_metadata() -> None:
    client = TestClient(app)
    app.state.lotus_core_client = _FakeLotusCoreClient()
    response = client.post(
        "/analytics/risk/concentration",
        json={
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "simulation_changes": [
                    {"security_id": "SEC_A", "transaction_type": "BUY", "quantity": 10}
                ],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "simulation"
    assert body["risk_proxy"]["hhi_current"] == 5200.0
    assert body["risk_proxy"]["hhi_proposed"] == 8200.0
    assert body["metadata"]["simulation_session_id"] == "SIM_0001"
    assert body["metadata"]["simulation_session_version"] == 3
