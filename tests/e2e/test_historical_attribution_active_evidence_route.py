"""Shipped Risk HTTP journey consuming the v1 Performance active group contract."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.contracts.downstream_authority import DownstreamAuthority
from app.main import app
from tests.support.app_runtime import override_app_runtime
from tests.support.historical_attribution_fakes import (
    RecordingHistoricalAttributionCoreClient,
    build_stateful_attribution_returns_client,
)
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient

DATES = ["2026-01-02", "2026-01-05", "2026-01-06"]
PORTFOLIO = [Decimal(".01"), Decimal("-.005"), Decimal(".004")]
BENCHMARK = [Decimal(".008"), Decimal("-.003"), Decimal(".003")]
P_WEIGHT_A = Decimal(".6")
P_WEIGHT_B = Decimal(".4")
B_WEIGHT_A = Decimal(".55")
B_WEIGHT_B = Decimal(".45")


def _source_response(request: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    aggregates: list[dict[str, str]] = []
    for index, day in enumerate(DATES):
        p = PORTFOLIO[index]
        b = BENCHMARK[index]
        p_delta = [Decimal(".004"), Decimal(".002"), Decimal("-.003")][index]
        b_delta = [Decimal(".001"), Decimal("-.002"), Decimal(".002")][index]
        p_a, p_b = p + p_delta, p - P_WEIGHT_A / P_WEIGHT_B * p_delta
        b_a, b_b = b + b_delta, b - B_WEIGHT_A / B_WEIGHT_B * b_delta
        for label, p_group, b_group, p_weight, b_weight in (
            ("TECH", p_a, b_a, P_WEIGHT_A, B_WEIGHT_A),
            ("HEALTH", p_b, b_b, P_WEIGHT_B, B_WEIGHT_B),
        ):
            rows.append(
                {
                    "date": day,
                    "group_id": f"SECTOR:{label.casefold()}",
                    "group_label": label,
                    "portfolio_group_return": str(p_group),
                    "benchmark_group_return": str(b_group),
                    "portfolio_weight": str(p_weight),
                    "benchmark_weight": str(b_weight),
                    "active_contribution": str(p_weight * p_group - b_weight * b_group),
                }
            )
        aggregates.append(
            {
                "date": day,
                "portfolio_return": str(p),
                "weighted_portfolio_return": str(p),
                "portfolio_reconciliation_delta": "0",
                "benchmark_return": str(b),
                "active_return": str(p - b),
                "group_active_contribution_delta": "0",
            }
        )
    return {
        **request,
        "contract_version": "v1",
        "benchmark_id": "BMK_GLOBAL_BALANCED_60_40",
        "return_basis": "SOURCE_POSITION_AND_BENCHMARK_COMPONENT_GROSS_TWR",
        "valuation_basis": "SOURCE_REPORTED_BEGINNING_AND_ENDING_MARKET_VALUES",
        "weight_basis": "SIGNED_BEGINNING_CAPITAL_AND_BENCHMARK_BOP_WEIGHT",
        "coverage": {
            "status": "COMPLETE",
            "reason_codes": [],
            "observed_dates": DATES,
            "reconciliation_tolerance": "0.000001",
        },
        "aggregate_returns": aggregates,
        "rows": rows,
        "source_lineage": {
            "execution_id": request["calculation_id"],
            "tenant_scope": "ADMITTED_TENANT",
            "source_cut_id": "sha256:" + "b" * 64,
            "upstream_revision_status": "NOT_PROVIDED_BY_SOURCE",
            "snapshots": [
                {
                    "upstream_endpoint": "/integration/portfolios/p/analytics/position-timeseries",
                    "source_identifier": "DEMO_DPM_EUR_001",
                    "as_of_date": DATES[-1],
                    "request_fingerprint": "sha256:req",
                    "response_fingerprint": "sha256:resp",
                    "retrieval_status": "200",
                }
            ],
        },
    }


class _ActiveEvidenceClient(RecordingLotusPerformanceClient):
    def __init__(self, *, mutate: bool = False) -> None:
        baseline = build_stateful_attribution_returns_client()
        assert baseline.benchmark_exposure_context_payload is not None
        super().__init__(
            response_payload=baseline.response_payload,
            benchmark_exposure_context_payload={
                **baseline.benchmark_exposure_context_payload,
                "reporting_currency": "USD",
            },
        )
        self.active_calls: list[dict[str, Any]] = []
        self.mutate = mutate

    async def get_group_return_evidence(
        self,
        *,
        request_payload: dict[str, Any],
        authority: DownstreamAuthority,
    ) -> dict[str, Any]:
        self.active_calls.append(
            {
                "request_payload": request_payload,
                "tenant_id": authority.tenant_id,
                "correlation_id": authority.correlation_id,
            }
        )
        response = _source_response(request_payload)
        if self.mutate:
            response["rows"][0]["active_contribution"] = "999"
        return response


def _request() -> dict[str, Any]:
    return {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": DATES[-1],
            "reporting_currency": "USD",
            "net_or_gross": "GROSS",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "attribution_options": {
                "attribution_types": ["ACTIVE_RISK"],
                "metrics": ["TRACKING_ERROR"],
                "grouping_dimensions": ["SECTOR"],
            },
        },
    }


def test_stateful_route_uses_admitted_empirical_active_economics() -> None:
    performance = _ActiveEvidenceClient()
    with override_app_runtime(
        lotus_performance_client=performance,
        lotus_core_client=RecordingHistoricalAttributionCoreClient(),
    ):
        response = TestClient(app).post(
            "/analytics/risk/historical-attribution",
            headers={"X-Tenant-Id": "tenant-a", "X-Correlation-Id": "active-evidence-route"},
            json=_request(),
        )
    assert response.status_code == 200, response.text
    result = response.json()
    item = result["results"]["YTD"]["attribution_sets"][0]
    assert item["risk_basis"] == "empirical_group_returns"
    assert result["metadata"]["calculation_supportability"]["state"] == "ready"
    assert item["reconciled_sum"] == pytest.approx(item["total_value"], abs=1e-12)
    assert item["residual"] == pytest.approx(0, abs=1e-12)
    assert {row["group_key"] for row in item["contributors"]} == {"SECTOR_TECH", "SECTOR_HEALTH"}
    assert len(performance.active_calls) == 1
    call = performance.active_calls[0]
    assert call["tenant_id"] == "tenant-a"
    assert call["correlation_id"] == "active-evidence-route"
    assert call["request_payload"]["window"] == {"start_date": DATES[0], "end_date": DATES[-1]}
    assert result["metadata"]["upstream_request_fingerprints"].get(
        "lotus-performance:/integration/attribution/group-return-evidence/v1"
    )
    # Execution UUIDs vary, but the economic request and accepted source cut do not.
    with override_app_runtime(
        lotus_performance_client=performance,
        lotus_core_client=RecordingHistoricalAttributionCoreClient(),
    ):
        replay = TestClient(app).post(
            "/analytics/risk/historical-attribution",
            headers={"X-Tenant-Id": "tenant-a", "X-Correlation-Id": "active-evidence-replay"},
            json=_request(),
        )
    assert replay.status_code == 200, replay.text
    assert (
        performance.active_calls[0]["request_payload"]["calculation_id"]
        != performance.active_calls[1]["request_payload"]["calculation_id"]
    )
    assert (
        replay.json()["metadata"]["upstream_request_fingerprints"]
        == result["metadata"]["upstream_request_fingerprints"]
    )
    assert (
        replay.json()["metadata"]["request_fingerprint"]
        == result["metadata"]["request_fingerprint"]
    )


def test_net_request_cannot_be_mislabeled_as_gross_empirical() -> None:
    performance = _ActiveEvidenceClient()
    payload = _request()
    payload["stateful_input"]["net_or_gross"] = "NET"
    with override_app_runtime(
        lotus_performance_client=performance,
        lotus_core_client=RecordingHistoricalAttributionCoreClient(),
    ):
        response = TestClient(app).post(
            "/analytics/risk/historical-attribution",
            headers={"X-Tenant-Id": "tenant-a"},
            json=payload,
        )
    assert response.status_code == 200, response.text
    assert performance.active_calls == []
    assert response.json()["results"]["YTD"]["attribution_sets"][0]["risk_basis"] == "weight_proxy"


def test_stateful_route_refuses_post_source_arithmetic_corruption() -> None:
    with override_app_runtime(
        lotus_performance_client=_ActiveEvidenceClient(mutate=True),
        lotus_core_client=RecordingHistoricalAttributionCoreClient(),
    ):
        response = TestClient(app).post(
            "/analytics/risk/historical-attribution",
            headers={"X-Tenant-Id": "tenant-a"},
            json=_request(),
        )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_INVALID_RESPONSE"
