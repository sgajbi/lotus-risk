"""Registered-route refusal of incomplete or incoherent benchmark exposures."""

from typing import Protocol, TypedDict

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.support.app_runtime import override_app_runtime
from tests.support.historical_attribution_fakes import (
    RecordingHistoricalAttributionCoreClient,
    build_benchmark_exposure_context_response,
    build_stateful_attribution_returns_client,
)
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient


class _ErrorDetails(TypedDict, total=False):
    service: str
    operation: str


class _ErrorBody(TypedDict):
    code: str
    message: str
    correlation_id: str
    details: _ErrorDetails


class _ErrorEnvelope(TypedDict):
    error: _ErrorBody


class _TestResponse(Protocol):
    status_code: int

    def json(self) -> _ErrorEnvelope: ...


def _post_stateful_active_risk(
    benchmark_context: dict[str, object],
) -> tuple[_TestResponse, RecordingLotusPerformanceClient]:
    performance_client = build_stateful_attribution_returns_client()
    performance_client.benchmark_exposure_context_payload = benchmark_context
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=RecordingHistoricalAttributionCoreClient(),
    ):
        response = TestClient(app).post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-benchmark-quality", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["ACTIVE_RISK"],
                        "metrics": ["TRACKING_ERROR"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )
    return response, performance_client


def test_stateful_active_risk_refuses_incomplete_benchmark_exposure_source() -> None:
    benchmark_context = build_benchmark_exposure_context_response()
    metadata = dict(benchmark_context["metadata"])
    metadata["exposure_source_quality"] = {
        "status": "incomplete",
        "omitted_component_count": 0,
        "omitted_point_count": 1,
        "reason_codes": ["MISSING_COMPONENT_WEIGHT"],
        "omissions": [
            {
                "component_id": "IDX_GLOBAL_BONDS",
                "series_date": "2026-01-05",
                "reason_code": "MISSING_COMPONENT_WEIGHT",
            }
        ],
        "omissions_truncated": False,
    }
    response, performance_client = _post_stateful_active_risk(
        {**benchmark_context, "metadata": metadata}
    )

    assert response.status_code == 424
    body = response.json()["error"]
    assert body["code"] == "FAILED_DEPENDENCY"
    assert body["message"] == "Required upstream dependency data is unavailable."
    assert body["correlation_id"] == "corr-benchmark-quality"
    assert body["details"]["service"] == "lotus-performance"
    assert body["details"]["operation"] == "/integration/benchmarks/exposure-context"
    assert performance_client.benchmark_exposure_context_calls


@pytest.mark.parametrize("mutation", ["missing_row_key", "foreign_portfolio"])
def test_stateful_active_risk_refuses_complete_but_invalid_context(mutation: str) -> None:
    benchmark_context = build_benchmark_exposure_context_response()
    if mutation == "missing_row_key":
        rows = list(benchmark_context["rows"])
        rows[0] = {key: value for key, value in rows[0].items() if key != "group_key"}
        benchmark_context["rows"] = rows
    else:
        benchmark_context["portfolio_id"] = "FOREIGN_PORTFOLIO"
    response, performance_client = _post_stateful_active_risk(benchmark_context)

    assert response.status_code == 502
    body = response.json()["error"]
    assert body["code"] == "UPSTREAM_INVALID_RESPONSE"
    assert body["correlation_id"] == "corr-benchmark-quality"
    assert performance_client.benchmark_exposure_context_calls
