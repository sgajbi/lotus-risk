from __future__ import annotations

from fastapi.testclient import TestClient

from app.contracts.risk_event_cohort_inputs import (
    RISK_EVENT_MAX_CANDIDATE_PORTFOLIOS,
    RISK_EVENT_MAX_EXPOSURE_BUCKETS_PER_PORTFOLIO,
)
from app.main import app


def test_risk_event_affected_cohort_endpoint_returns_source_contract() -> None:
    client = TestClient(app)

    response = client.post(
        "/analytics/risk/risk-event-cohorts/evaluate",
        json={
            "risk_event_id": "RISK_EVENT_2026_Q2_RATES_UP",
            "as_of_date": "2026-05-10",
            "minimum_impact_score": 0.05,
            "portfolios": [
                {
                    "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                    "mandate_id": "MANDATE-PB-SG-GLOBAL-BAL-001",
                    "portfolio_manager_id": "pm-singapore-01",
                    "exposure_weights": {
                        "EQUITY": 0.55,
                        "FIXED_INCOME": 0.35,
                        "CASH": 0.10,
                    },
                }
            ],
        },
        headers={"X-Correlation-Id": "corr-risk-event-cohort"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_event_id"] == "RISK_EVENT_2026_Q2_RATES_UP"
    assert body["metadata"]["product_name"] == "RiskEventAffectedCohort"
    assert body["metadata"]["calculation_supportability"] == "ready"
    assert body["affected_portfolios"][0]["portfolio_id"] == "PB_SG_GLOBAL_BAL_001"
    assert body["affected_portfolios"][0]["source_ref"].startswith("risk-event-cohort:")


def test_risk_event_affected_cohort_endpoint_preserves_exclusion_lineage() -> None:
    client = TestClient(app)

    response = client.post(
        "/analytics/risk/risk-event-cohorts/evaluate",
        json={
            "risk_event_id": "RISK_EVENT_2026_Q2_RATES_UP",
            "as_of_date": "2026-05-10",
            "minimum_impact_score": 0.05,
            "portfolios": [
                {
                    "portfolio_id": "PB_SG_LOW_RISK_002",
                    "mandate_id": "MANDATE-PB-SG-LOW-RISK-002",
                    "portfolio_manager_id": "pm-singapore-01",
                    "exposure_weights": {
                        "FIXED_INCOME": 0.10,
                        "CASH": 0.90,
                    },
                }
            ],
        },
        headers={"X-Correlation-Id": "corr-risk-event-cohort-excluded"},
    )

    assert response.status_code == 200
    excluded = response.json()["excluded_portfolios"][0]
    assert excluded == {
        "portfolio_id": "PB_SG_LOW_RISK_002",
        "mandate_id": "MANDATE-PB-SG-LOW-RISK-002",
        "portfolio_manager_id": "pm-singapore-01",
        "impact_score": 0.015,
        "dominant_bucket": "FIXED_INCOME",
        "bucket_impacts": {"FIXED_INCOME": -0.015, "CASH": 0.0},
        "source_ref": (
            "risk-event-cohort:RISK_EVENT_2026_Q2_RATES_UP:2026-05-10:PB_SG_LOW_RISK_002"
        ),
        "reason_codes": ["RISK_EVENT_BELOW_THRESHOLD"],
    }


def test_capabilities_include_risk_event_cohort_workflow() -> None:
    client = TestClient(app)

    response = client.get("/integration/capabilities")

    assert response.status_code == 200
    workflows = {workflow["workflow_key"]: workflow for workflow in response.json()["workflows"]}
    assert workflows["risk_event_affected_cohort"]["endpoint_path"] == (
        "/analytics/risk/risk-event-cohorts/evaluate"
    )
    assert workflows["risk_event_affected_cohort"]["support_status"] == "partial"


def test_openapi_documents_risk_event_cohort_workload_bounds() -> None:
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    components = response.json()["components"]["schemas"]
    request_schema = components["RiskEventAffectedCohortRequest"]
    portfolio_schema = components["RiskEventPortfolioExposure"]
    excluded_schema = components["RiskEventExcludedPortfolio"]
    assert request_schema["properties"]["portfolios"]["maxItems"] == (
        RISK_EVENT_MAX_CANDIDATE_PORTFOLIOS
    )
    assert portfolio_schema["properties"]["exposure_weights"]["maxProperties"] == (
        RISK_EVENT_MAX_EXPOSURE_BUCKETS_PER_PORTFOLIO
    )
    assert "source_ref" in excluded_schema["properties"]
    assert "dominant_bucket" in excluded_schema["properties"]
    assert "bucket_impacts" in excluded_schema["properties"]
