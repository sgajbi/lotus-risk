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
            "exposure_components": [
                {
                    "security_id": "FO_EQ_AAPL_US",
                    "display_name": "Apple Inc.",
                    "bucket": "EQUITY",
                    "weight": 0.30,
                },
                {
                    "security_id": "FO_EQ_MSFT_US",
                    "display_name": "Microsoft Corporation",
                    "bucket": "EQUITY",
                    "weight": 0.25,
                },
                {
                    "security_id": "FO_BOND_UST_2030",
                    "display_name": "United States Treasury 3.875% 2030",
                    "bucket": "FIXED_INCOME",
                    "weight": 0.35,
                },
                {
                    "security_id": "CASH_USD_BOOK_OPERATING",
                    "display_name": "USD Operating Cash",
                    "bucket": "CASH",
                    "weight": 0.10,
                },
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
    assert body["governance_evidence"]["cio_approval_status"] == "approved"
    assert body["governance_evidence"]["effective_period_status"] == "active"
    assert body["governance_evidence"]["applicability_status"] == "applicable"
    assert body["governance_evidence"]["portfolio_applicability_ref"] == (
        "CIO-REGIME-2026-Q2-APPROVAL-APP-PB_SG_GLOBAL_BAL_001"
    )
    assert body["reason_codes"] == ["REGIME_SCENARIO_PACK_READY"]
    growth_slowdown = next(
        scenario
        for scenario in body["scenario_results"]
        if scenario["scenario_id"] == "growth_slowdown"
    )
    assert growth_slowdown["position_contributions"][0] == {
        "security_id": "FO_EQ_AAPL_US",
        "display_name": "Apple Inc.",
        "bucket": "EQUITY",
        "weight": 0.3,
        "shock_pct": -0.12,
        "contribution_loss_pct": 0.036,
    }


def test_capabilities_include_regime_scenario_pack_workflow() -> None:
    client = TestClient(app)

    response = client.get("/integration/capabilities")

    assert response.status_code == 200
    workflows = {workflow["workflow_key"]: workflow for workflow in response.json()["workflows"]}
    assert workflows["regime_scenario_pack_evaluation"]["endpoint_path"] == (
        "/analytics/risk/regime-scenario-pack/evaluate"
    )
    assert workflows["regime_scenario_pack_evaluation"]["support_status"] == "full"
    assert (
        "returns source-owned worst-case loss, per-security contribution rows when supplied, CIO approval/effective-period/applicability posture, policy breach posture, and lineage"
        in workflows["regime_scenario_pack_evaluation"]["notes"]
    )


def test_openapi_documents_regime_scenario_pack_component_rows() -> None:
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    components = response.json()["components"]["schemas"]
    request_schema = components["RegimeScenarioPackRequest"]
    result_schema = components["ScenarioResult"]
    assert "exposure_components" in request_schema["properties"]
    assert (
        "component weights must reconcile"
        in request_schema["properties"]["exposure_components"]["description"]
    )
    assert "position_contributions" in result_schema["properties"]
    assert (
        "not a full repricing model"
        in result_schema["properties"]["position_contributions"]["description"]
    )
    response_schema = components["RegimeScenarioPackResponse"]
    assert "governance_evidence" in response_schema["properties"]
    assert (
        "CIO approval, effective-period, and portfolio-applicability evidence"
        in response_schema["properties"]["governance_evidence"]["description"]
    )
