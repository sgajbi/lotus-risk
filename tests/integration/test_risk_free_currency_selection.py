"""Route proof for stateful risk-free currency and domain dependency selection."""

from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.risk import helpers as risk_helpers
from tests.support.app_runtime import override_app_runtime
from tests.support.lotus_core_fakes import RecordingLotusCoreReferenceClient
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import (
    RISK_STATEFUL_RETURNS,
    build_returns_series_response,
)
from tests.support.risk_free_series_payloads import build_risk_free_series_response


def _risk_free_payload() -> dict[str, object]:
    return build_risk_free_series_response(
        currency="EUR",
        as_of_date="2025-01-07",
        start_date="2025-01-02",
        end_date="2025-01-07",
        points=[
            {
                "series_date": day,
                "value": "0.025",
                "value_convention": "annualized_rate",
            }
            for day in ("2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07")
        ],
    )


def test_risk_calculate_stateful_sharpe_binds_core_currency_to_both_sources() -> None:
    source_response = build_returns_series_response(portfolio_returns=RISK_STATEFUL_RETURNS)
    source_response["valuation_context"] = {"reporting_currency": "CHF"}
    performance_client = RecordingLotusPerformanceClient(response_payload=source_response)
    core_client = RecordingLotusCoreReferenceClient(
        snapshot_response={"valuation_context": {"reporting_currency": "EUR"}},
        risk_free_response=_risk_free_payload(),
    )
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        response = TestClient(app).post(
            "/analytics/risk/calculate",
            headers={"X-Correlation-Id": "corr-risk-core-currency", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2025-01-07",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "metrics": ["SHARPE"],
                },
            },
        )

    assert response.status_code == 200
    assert core_client.snapshot_calls[0]["tenant_id"] == "tenant-a"
    performance_payload = cast(dict[str, Any], performance_client.calls[0]["request_payload"])
    risk_free_payload = cast(dict[str, Any], core_client.risk_free_calls[0]["request_payload"])
    assert performance_payload["reporting_currency"] == "EUR"
    assert risk_free_payload["currency"] == "EUR"
    assert response.json()["scope"]["reporting_currency"] == "EUR"
    assert (
        "lotus-core:/integration/portfolios/{portfolio_id}/core-snapshot"
        in response.json()["metadata"]["upstream_request_fingerprints"]
    )


def test_risk_calculate_route_uses_domain_risk_free_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        risk_helpers,
        "RISK_METRICS_REQUIRING_RISK_FREE",
        {"SHARPE", "VOLATILITY"},
    )
    performance_client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(portfolio_returns=RISK_STATEFUL_RETURNS)
    )
    core_client = RecordingLotusCoreReferenceClient(risk_free_response=_risk_free_payload())
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        response = TestClient(app).post(
            "/analytics/risk/calculate",
            headers={"X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2025-01-07",
                    "reporting_currency": "USD",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "metrics": ["VOLATILITY"],
                },
            },
        )

    assert response.status_code == 200
    risk_free_payload = cast(dict[str, Any], core_client.risk_free_calls[0]["request_payload"])
    assert risk_free_payload["currency"] == "USD"
