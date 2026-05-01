from __future__ import annotations

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY, generate_latest

from app.main import app
from app.observability_contracts import (
    RISK_ANALYTICS_FRESHNESS_METRIC_LABELS,
    RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS,
)
from tests.support.app_runtime import override_app_runtime
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import build_returns_series_response


client = TestClient(app)
FORBIDDEN_SUPPORTABILITY_METRIC_LABELS = {
    "portfolio_id",
    "account_id",
    "client_id",
    "correlation_id",
    "trace_id",
    "transaction_id",
    "security_id",
    "request_body",
    "response_body",
}


def _risk_stateless_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-03-31", "net_or_gross": "NET"},
            "portfolio_open_date": "2026-01-02",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY"],
            "returns": [
                {"date": "2026-01-02", "value": 0.5},
                {"date": "2026-01-05", "value": -0.2},
            ],
        },
    }


def _risk_stateful_payload() -> dict[str, object]:
    return {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-03-31",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY"],
        },
    }


def test_metrics_expose_endpoint_execution_mode_and_outcome() -> None:
    response = client.post("/analytics/risk/calculate", json=_risk_stateless_payload())
    assert response.status_code == 200
    supportability = response.json()["metadata"]["calculation_supportability"]
    assert supportability["metric_labels"] == list(RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS)

    metrics = client.get("/metrics").text

    assert 'lotus_risk_endpoint_executions_total{endpoint="risk/calculate"' in metrics
    assert 'input_mode="stateless"' in metrics
    assert 'outcome="success"' in metrics
    assert "lotus_risk_endpoint_execution_seconds_bucket" in metrics
    assert "lotus_risk_calculation_supportability_total{" in metrics
    assert 'operation="risk/calculate"' in metrics
    assert 'supportability_state="stale"' in metrics
    assert 'reason="stale_source_observations"' in metrics
    assert 'freshness_bucket="stale"' in metrics
    assert "lotus_analytics_freshness_bucket_total" in metrics
    assert (
        'lotus_analytics_freshness_bucket_total{freshness_bucket="stale",'
        'operation="risk/calculate",service="lotus-risk",supportability_state="stale"}'
    ) in metrics


def test_supportability_metrics_use_only_bounded_labels() -> None:
    response = client.post("/analytics/risk/calculate", json=_risk_stateless_payload())
    assert response.status_code == 200

    metrics = generate_latest(REGISTRY).decode("utf-8")
    supportability_lines = [
        line
        for line in metrics.splitlines()
        if line.startswith("lotus_risk_calculation_supportability_total{")
        and 'operation="risk/calculate"' in line
    ]
    freshness_lines = [
        line
        for line in metrics.splitlines()
        if line.startswith("lotus_analytics_freshness_bucket_total{")
        and 'operation="risk/calculate"' in line
    ]

    assert supportability_lines
    assert freshness_lines
    supportability_line = supportability_lines[-1]
    freshness_line = freshness_lines[-1]

    for label in RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS:
        assert f"{label}=" in supportability_line
    for label in RISK_ANALYTICS_FRESHNESS_METRIC_LABELS:
        assert f"{label}=" in freshness_line
    for forbidden_label in FORBIDDEN_SUPPORTABILITY_METRIC_LABELS:
        assert f"{forbidden_label}=" not in supportability_line
        assert f"{forbidden_label}=" not in freshness_line


def test_metrics_expose_stateful_endpoint_execution_mode() -> None:
    performance_client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=[
                ("2026-01-02", "0.005"),
                ("2026-01-05", "-0.002"),
            ]
        )
    )

    with override_app_runtime(lotus_performance_client=performance_client):
        response = client.post(
            "/analytics/risk/calculate",
            json=_risk_stateful_payload(),
            headers={"X-Correlation-Id": "corr-observability"},
        )

    assert response.status_code == 200
    metrics = client.get("/metrics").text

    assert 'input_mode="stateful"' in metrics
