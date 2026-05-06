from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_regime_scenario_pack_endpoint_returns_evaluation_contract() -> None:
    client = TestClient(app)

    response = client.post(
        "/analytics/risk/regime-scenario-pack/evaluate",
        json={
            "scenario_pack_id": "CIO_REGIME_2026_Q2",
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "as_of_date": "2026-05-03",
            "maximum_allowed_loss_pct": 0.12,
            "exposures": [
                {"bucket": "EQUITY", "weight": 0.55},
                {"bucket": "FIXED_INCOME", "weight": 0.35},
                {"bucket": "CASH", "weight": 0.10},
            ],
        },
        headers={"X-Correlation-Id": "corr-scenario-api"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scenario_pack_id"] == "CIO_REGIME_2026_Q2"
    assert body["worst_case_loss_pct"] == 0.106
    assert body["metadata"]["product_name"] == "RegimeScenarioPackEvaluation"
    assert body["metadata"]["calculation_supportability"] == "ready"
    assert body["reason_codes"] == ["REGIME_SCENARIO_PACK_READY"]


def test_capabilities_include_regime_scenario_pack_workflow() -> None:
    client = TestClient(app)

    response = client.get("/integration/capabilities")

    assert response.status_code == 200
    workflows = {workflow["workflow_key"]: workflow for workflow in response.json()["workflows"]}
    assert workflows["regime_scenario_pack_evaluation"]["endpoint_path"] == (
        "/analytics/risk/regime-scenario-pack/evaluate"
    )
    assert workflows["regime_scenario_pack_evaluation"]["support_status"] == "full"
