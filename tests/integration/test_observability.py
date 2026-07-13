from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from prometheus_client import REGISTRY, generate_latest

from app.main import app
from app.observability_contracts import (
    RISK_ANALYTICS_FRESHNESS_METRIC_LABELS,
    RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS,
)
from tests.support.app_runtime import override_app_runtime
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import build_returns_series_response
from app.services.endpoint_observation import observed_endpoint


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


class _ObservedRouteResponse(BaseModel):
    status: str


def _mandate_health_payload() -> dict[str, object]:
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


def _regime_scenario_payload() -> dict[str, object]:
    return {
        "scenario_pack_id": "CIO_REGIME_2026_Q2",
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "as_of_date": "2026-05-03",
        "maximum_allowed_loss_pct": 0.12,
        "exposures": [
            {"bucket": "EQUITY", "weight": 0.55},
            {"bucket": "FIXED_INCOME", "weight": 0.35},
            {"bucket": "CASH", "weight": 0.10},
        ],
    }


def _risk_event_cohort_payload() -> dict[str, object]:
    return {
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
    }


def _endpoint_execution_metric_value(
    *,
    endpoint: str,
    input_mode: str,
    outcome: str,
) -> float:
    metric_text = generate_latest(REGISTRY).decode("utf-8")
    for line in metric_text.splitlines():
        if not line.startswith("lotus_risk_endpoint_executions_total{"):
            continue
        if (
            f'endpoint="{endpoint}"' in line
            and f'input_mode="{input_mode}"' in line
            and f'outcome="{outcome}"' in line
        ):
            return float(line.rsplit(" ", maxsplit=1)[1])
    return 0.0


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


def test_source_product_endpoints_emit_supportability_metrics_without_sensitive_labels() -> None:
    calls = [
        (
            "/analytics/risk/mandate-health-context",
            _mandate_health_payload(),
            "mandate-risk-health-context",
            "attention",
            "source_product_attention",
        ),
        (
            "/analytics/risk/regime-scenario-pack/evaluate",
            _regime_scenario_payload(),
            "regime-scenario-pack",
            "ready",
            "calculation_complete",
        ),
        (
            "/analytics/risk/risk-event-cohorts/evaluate",
            _risk_event_cohort_payload(),
            "risk-event-cohort",
            "ready",
            "calculation_complete",
        ),
    ]

    for path, payload, _, _, _ in calls:
        response = client.post(path, json=payload)
        assert response.status_code == 200

    metrics = generate_latest(REGISTRY).decode("utf-8")
    for _, _, operation, state, reason in calls:
        supportability_lines = [
            line
            for line in metrics.splitlines()
            if line.startswith("lotus_risk_calculation_supportability_total{")
            and f'operation="{operation}"' in line
            and f'supportability_state="{state}"' in line
            and f'reason="{reason}"' in line
            and 'freshness_bucket="unknown"' in line
        ]
        freshness_lines = [
            line
            for line in metrics.splitlines()
            if line.startswith("lotus_analytics_freshness_bucket_total{")
            and f'operation="{operation}"' in line
            and f'supportability_state="{state}"' in line
            and 'freshness_bucket="unknown"' in line
        ]
        assert supportability_lines
        assert freshness_lines
        for forbidden_label in FORBIDDEN_SUPPORTABILITY_METRIC_LABELS:
            assert f"{forbidden_label}=" not in supportability_lines[-1]
            assert f"{forbidden_label}=" not in freshness_lines[-1]


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


def test_endpoint_execution_metric_records_response_model_validation_failure() -> None:
    test_app = FastAPI()

    @test_app.post(
        "/analytics/risk/invalid-response",
        response_model=_ObservedRouteResponse,
    )
    async def invalid_response() -> _ObservedRouteResponse:
        return await observed_endpoint(
            endpoint="risk/calculate",
            input_mode="stateless",
            response_model=_ObservedRouteResponse,
            operation=lambda: {"unexpected": "shape"},
        )

    response_client = TestClient(test_app, raise_server_exceptions=False)
    success_before = _endpoint_execution_metric_value(
        endpoint="risk/calculate",
        input_mode="stateless",
        outcome="success",
    )
    failure_before = _endpoint_execution_metric_value(
        endpoint="risk/calculate",
        input_mode="stateless",
        outcome="failure",
    )

    response = response_client.post("/analytics/risk/invalid-response", json={})

    assert response.status_code == 500
    assert (
        _endpoint_execution_metric_value(
            endpoint="risk/calculate",
            input_mode="stateless",
            outcome="failure",
        )
        >= failure_before + 1
    )
    assert (
        _endpoint_execution_metric_value(
            endpoint="risk/calculate",
            input_mode="stateless",
            outcome="success",
        )
        == success_before
    )
