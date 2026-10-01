from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.contracts.mandate_health import (
    MandateRiskHealthContextRequest,
    MandateRiskHealthContextResponse,
    MandateRiskHealthMethodologyPosture,
    MandateRiskHealthSourceMetric,
)
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


def test_mandate_health_contract_facade_preserves_public_imports() -> None:
    assert MandateRiskHealthContextRequest.__name__ == "MandateRiskHealthContextRequest"
    assert MandateRiskHealthContextResponse.__name__ == "MandateRiskHealthContextResponse"
    assert MandateRiskHealthSourceMetric.__name__ == "MandateRiskHealthSourceMetric"
    assert MandateRiskHealthMethodologyPosture.__name__ == "MandateRiskHealthMethodologyPosture"


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


@pytest.mark.parametrize(
    "both_series_empty",
    [False, True],
)
def test_mandate_risk_health_context_marks_missing_portfolio_history_unavailable(
    both_series_empty: bool,
) -> None:
    payload = _request_payload()
    payload["returns"] = []
    if both_series_empty:
        payload["benchmark_returns"] = []

    response = evaluate_mandate_risk_health_context(
        MandateRiskHealthContextRequest.model_validate(payload)
    )

    assert response.health_state == "unavailable"
    assert response.threshold_breached is None
    assert response.source_metric.annualized_tracking_error is None
    assert response.source_metric.aligned_observation_count == 0
    assert response.request_fingerprint.startswith("sha256:")
    assert response.source_request_fingerprint.startswith("sha256:")
    assert "MANDATE_RISK_HEALTH_TRACKING_ERROR_UNAVAILABLE" in response.reason_codes
    assert "MANDATE_RISK_HEALTH_PORTFOLIO_HISTORY_UNAVAILABLE" in response.reason_codes


def test_mandate_risk_health_context_marks_one_aligned_observation_unavailable() -> None:
    payload = _request_payload()
    payload["benchmark_returns"] = [{"date": "2026-01-02", "value": 0.10}]

    response = evaluate_mandate_risk_health_context(
        MandateRiskHealthContextRequest.model_validate(payload)
    )

    assert response.health_state == "unavailable"
    assert response.threshold_breached is None
    assert response.source_metric.annualized_tracking_error is None
    assert "MANDATE_RISK_HEALTH_PORTFOLIO_HISTORY_UNAVAILABLE" not in response.reason_codes


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


def test_mandate_risk_health_context_zero_tracking_error_at_zero_threshold_is_ready() -> None:
    payload = _request_payload()
    payload["returns"] = [
        {"date": "2026-01-02", "value": 0.0},
        {"date": "2026-01-03", "value": 0.0},
        {"date": "2026-01-04", "value": 0.0},
    ]
    returns = payload["returns"]
    assert isinstance(returns, list)
    payload["benchmark_returns"] = list(returns)
    payload["tracking_error_attention_threshold"] = "0"

    response = TestClient(app).post("/analytics/risk/mandate-health-context", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["health_state"] == "ready"
    assert body["threshold_breached"] is False
    assert body["source_metric"]["annualized_tracking_error"] == "0.0"


@pytest.mark.parametrize("both_series_empty", [False, True])
def test_mandate_risk_health_context_endpoint_returns_unavailable_for_empty_history(
    both_series_empty: bool,
) -> None:
    payload = _request_payload()
    payload["returns"] = []
    if both_series_empty:
        payload["benchmark_returns"] = []

    response = TestClient(app, raise_server_exceptions=False).post(
        "/analytics/risk/mandate-health-context", json=payload
    )

    assert response.status_code == 200
    body = response.json()
    assert body["health_state"] == "unavailable"
    assert body["threshold_breached"] is None
    assert body["source_metric"]["annualized_tracking_error"] is None
    assert body["source_metric"]["aligned_observation_count"] == 0
    assert "MANDATE_RISK_HEALTH_PORTFOLIO_HISTORY_UNAVAILABLE" in body["reason_codes"]


def test_mandate_risk_health_context_endpoint_remains_unavailable_for_out_of_period_history() -> (
    None
):
    payload = _request_payload()
    payload["returns"] = [
        {"date": "2025-12-20", "value": 0.25},
        {"date": "2025-12-21", "value": -0.10},
    ]
    payload["benchmark_returns"] = [
        {"date": "2025-12-20", "value": 0.10},
        {"date": "2025-12-21", "value": 0.05},
    ]

    response = TestClient(app, raise_server_exceptions=False).post(
        "/analytics/risk/mandate-health-context", json=payload
    )

    assert response.status_code == 200
    body = response.json()
    assert body["health_state"] == "unavailable"
    assert body["threshold_breached"] is None
    assert "MANDATE_RISK_HEALTH_PORTFOLIO_HISTORY_UNAVAILABLE" not in body["reason_codes"]


@pytest.mark.parametrize("series_name", ["returns", "benchmark_returns"])
def test_mandate_risk_health_context_endpoint_refuses_duplicate_source_dates(
    series_name: str,
) -> None:
    payload = _request_payload()
    points = payload[series_name]
    assert isinstance(points, list)
    points.append(dict(points[1]))

    response = TestClient(app).post("/analytics/risk/mandate-health-context", json=payload)

    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert details[0]["loc"] == ["body"]
    assert details[0]["msg"] == (
        f"Value error, duplicate return observation date in {series_name}: 2026-01-03"
    )


def test_capabilities_include_mandate_risk_health_context_workflow() -> None:
    client = TestClient(app)

    response = client.get("/integration/capabilities")

    assert response.status_code == 200
    workflows = {workflow["workflow_key"]: workflow for workflow in response.json()["workflows"]}
    workflow = workflows["mandate_risk_health_context"]
    assert workflow["endpoint_path"] == "/analytics/risk/mandate-health-context"
    assert workflow["support_status"] == "partial"
    assert workflow["supported_input_modes"] == ["stateless"]
