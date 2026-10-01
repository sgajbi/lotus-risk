"""Public attribution journey across complete and refused benchmark source states."""

from fastapi.testclient import TestClient

from app.main import app
from tests.support.app_runtime import override_app_runtime
from tests.support.historical_attribution_fakes import (
    RecordingHistoricalAttributionCoreClient,
    build_benchmark_exposure_context_response,
    build_stateful_attribution_returns_client,
)


def test_e2e_attribution_preserves_complete_then_refuses_incomplete_and_incoherent_source() -> None:
    performance_client = build_stateful_attribution_returns_client()
    complete = build_benchmark_exposure_context_response()
    payload = {
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
    }
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=RecordingHistoricalAttributionCoreClient(),
    ):
        client = TestClient(app)

        accepted = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Tenant-Id": "tenant-a", "X-Correlation-Id": "corr-complete"},
            json=payload,
        )

        incomplete_metadata = dict(complete["metadata"])
        incomplete_metadata["exposure_source_quality"] = {
            "status": "incomplete",
            "omitted_component_count": 1,
            "omitted_point_count": 0,
            "reason_codes": ["MISSING_COMPONENT_WEIGHT"],
            "omissions": [{"component_id": "IDX_GLOBAL_BONDS"}],
            "omissions_truncated": False,
        }
        performance_client.benchmark_exposure_context_payload = {
            **complete,
            "metadata": incomplete_metadata,
        }
        incomplete = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Tenant-Id": "tenant-a", "X-Correlation-Id": "corr-incomplete"},
            json=payload,
        )

        malformed = dict(complete)
        malformed["portfolio_id"] = "FOREIGN_PORTFOLIO"
        performance_client.benchmark_exposure_context_payload = malformed
        incoherent = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Tenant-Id": "tenant-a", "X-Correlation-Id": "corr-incoherent"},
            json=payload,
        )

    assert accepted.status_code == 200
    assert accepted.json()["results"]["YTD"]["attribution_sets"][0]["contributors"]
    assert incomplete.status_code == 424
    assert incomplete.json()["error"]["code"] == "FAILED_DEPENDENCY"
    assert incomplete.json()["error"]["correlation_id"] == "corr-incomplete"
    assert incoherent.status_code == 502
    assert incoherent.json()["error"]["code"] == "UPSTREAM_INVALID_RESPONSE"
    assert incoherent.json()["error"]["correlation_id"] == "corr-incoherent"
    assert [call["tenant_id"] for call in performance_client.benchmark_exposure_context_calls] == [
        "tenant-a",
        "tenant-a",
        "tenant-a",
    ]
