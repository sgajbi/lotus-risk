from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.contracts.mandate_health import MandateRiskHealthContextRequest
from app.main import app
from app.services.mandate_health_context import evaluate_mandate_risk_health_context


def _request_payload() -> dict[str, object]:
    return {
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "scope": {
            "as_of_date": "2026-02-27",
            "reporting_currency": "USD",
            "net_or_gross": "NET",
        },
        "period": {"type": "YTD", "name": "YTD"},
        "portfolio_open_date": "2024-01-01",
        "returns": [
            {"date": "2026-01-02", "value": 0.25},
            {"date": "2026-01-03", "value": -0.10},
            {"date": "2026-01-04", "value": 0.40},
        ],
        "benchmark_returns": [
            {"date": "2026-01-02", "value": 0.10},
            {"date": "2026-01-03", "value": 0.05},
            {"date": "2026-01-04", "value": 0.12},
        ],
        "tracking_error_attention_threshold": "0.01",
    }


def test_mandate_risk_health_context_uses_source_tracking_error_methodology() -> None:
    response = evaluate_mandate_risk_health_context(
        MandateRiskHealthContextRequest.model_validate(_request_payload())
    )

    assert response.product_name == "MandateRiskHealthContext"
    assert response.product_version == "v1"
    assert response.portfolio_id == "PB_SG_GLOBAL_BAL_001"
    assert response.period_name == "YTD"
    assert response.health_state == "attention"
    assert response.threshold_breached is True
    assert response.tracking_error_attention_threshold == Decimal("0.01")
    assert response.source_metric.metric_name == "TRACKING_ERROR"
    assert response.source_metric.annualized_tracking_error is not None
    assert response.source_metric.annualized_tracking_error > Decimal("0.01")
    assert response.source_metric.aligned_observation_count == 3
    assert response.methodology_posture.source_service == "lotus-risk"
    assert response.methodology_posture.source_metrics_product == "RiskMetricsReport:v1"
    assert response.methodology_posture.source_route == "/analytics/risk/calculate"
    assert response.request_fingerprint.startswith("sha256:")
    assert response.source_request_fingerprint.startswith("sha256:")
    assert "RISK_METHODOLOGY_SOURCE_OWNED" in response.reason_codes
    assert "MANDATE_RISK_HEALTH_TRACKING_ERROR_SOURCE_READY" in response.reason_codes
    assert "MANDATE_RISK_HEALTH_TRACKING_ERROR_THRESHOLD_BREACHED" in response.reason_codes


def test_mandate_risk_health_context_marks_ready_below_threshold() -> None:
    payload = _request_payload()
    payload["tracking_error_attention_threshold"] = "1.00"

    response = evaluate_mandate_risk_health_context(
        MandateRiskHealthContextRequest.model_validate(payload)
    )

    assert response.health_state == "ready"
    assert response.threshold_breached is False
    assert "MANDATE_RISK_HEALTH_TRACKING_ERROR_SOURCE_READY" in response.reason_codes
    assert "MANDATE_RISK_HEALTH_TRACKING_ERROR_THRESHOLD_BREACHED" not in response.reason_codes


def test_mandate_risk_health_context_marks_unavailable_when_tracking_error_unavailable() -> None:
    payload = _request_payload()
    payload["benchmark_returns"] = [
        {"date": "2025-12-20", "value": 0.10},
        {"date": "2025-12-21", "value": 0.12},
    ]

    response = evaluate_mandate_risk_health_context(
        MandateRiskHealthContextRequest.model_validate(payload)
    )

    assert response.health_state == "unavailable"
    assert response.threshold_breached is None
    assert response.source_metric.annualized_tracking_error is None
    assert "MANDATE_RISK_HEALTH_TRACKING_ERROR_UNAVAILABLE" in response.reason_codes


def test_mandate_risk_health_context_endpoint_returns_source_product() -> None:
    client = TestClient(app)

    response = client.post("/analytics/risk/mandate-health-context", json=_request_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["product_name"] == "MandateRiskHealthContext"
    assert body["methodology_posture"]["source_service"] == "lotus-risk"
    assert body["methodology_posture"]["source_metrics_product"] == "RiskMetricsReport:v1"
    assert body["health_state"] == "attention"
    assert body["threshold_breached"] is True


def test_capabilities_include_mandate_risk_health_context_workflow() -> None:
    client = TestClient(app)

    response = client.get("/integration/capabilities")

    assert response.status_code == 200
    workflows = {workflow["workflow_key"]: workflow for workflow in response.json()["workflows"]}
    workflow = workflows["mandate_risk_health_context"]
    assert workflow["endpoint_path"] == "/analytics/risk/mandate-health-context"
    assert workflow["support_status"] == "partial"
    assert workflow["supported_input_modes"] == ["stateless"]
