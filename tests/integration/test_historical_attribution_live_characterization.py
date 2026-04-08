from __future__ import annotations

import os
from datetime import date

import httpx
import pytest

from tests.support.live_returns_series import fetch_live_benchmark_exposure_context


def _live_enabled() -> bool:
    return os.getenv("LOTUS_RISK_RUN_LIVE_ATTRIBUTION") == "1"


pytestmark = pytest.mark.skipif(
    not _live_enabled(),
    reason="set LOTUS_RISK_RUN_LIVE_ATTRIBUTION=1 to run live attribution characterization",
)


RISK_BASE_URL = os.getenv("LOTUS_RISK_BASE_URL", "http://localhost:8130")
PERFORMANCE_BASE_URL = os.getenv("LOTUS_PERFORMANCE_BASE_URL", "http://localhost:8002")
PORTFOLIO_ID = os.getenv("LOTUS_RISK_LIVE_PORTFOLIO_ID", "PB_SG_GLOBAL_BAL_001")
AS_OF_DATE = date.fromisoformat(os.getenv("LOTUS_RISK_LIVE_AS_OF_DATE", "2026-03-31"))


def _benchmark_exposure_request(*, grouping_dimensions: list[str]) -> dict[str, object]:
    start_of_year = date(AS_OF_DATE.year, 1, 1)
    return {
        "portfolio_id": PORTFOLIO_ID,
        "as_of_date": AS_OF_DATE.isoformat(),
        "window": {
            "start_date": start_of_year.isoformat(),
            "end_date": AS_OF_DATE.isoformat(),
        },
        "frequency": "DAILY",
        "grouping_dimensions": grouping_dimensions,
        "page": {"page_size": 1000, "page_token": None},
    }


def test_live_benchmark_exposure_context_supports_sector_but_rejects_issuer() -> None:
    supported = fetch_live_benchmark_exposure_context(
        base_url=PERFORMANCE_BASE_URL,
        request_payload=_benchmark_exposure_request(grouping_dimensions=["SECTOR"]),
    )

    assert supported["source_service"] == "lotus-performance"
    assert supported["contract_version"] == "v1"
    assert supported["metadata"]["source_system"] == "lotus-core"
    assert supported["metadata"]["served_by"] == "lotus-performance"
    assert supported["rows"], "expected live sector benchmark exposure rows"
    assert {row["grouping_dimension"] for row in supported["rows"]} == {"SECTOR"}

    with httpx.Client(timeout=30.0) as client:
        rejected = client.post(
            f"{PERFORMANCE_BASE_URL}/integration/benchmarks/exposure-context",
            json=_benchmark_exposure_request(grouping_dimensions=["ISSUER"]),
        )

    assert rejected.status_code == 422
    body = rejected.json()
    detail = body.get("detail")
    assert isinstance(detail, list)
    assert any("grouping_dimensions=ISSUER" in item["msg"] for item in detail)


def test_live_stateful_historical_attribution_rejects_issuer_at_request_boundary() -> None:
    payload = {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": PORTFOLIO_ID,
            "as_of_date": AS_OF_DATE.isoformat(),
            "periods": [{"type": "YTD", "name": "YTD"}],
            "attribution_options": {
                "attribution_types": ["ACTIVE_RISK"],
                "metrics": ["TRACKING_ERROR"],
                "grouping_dimensions": ["ISSUER"],
            },
        },
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{RISK_BASE_URL}/analytics/risk/historical-attribution",
            json=payload,
        )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_REQUEST"
    assert error["message"] == "Request validation failed"
    assert any("grouping_dimension=ISSUER" in detail["msg"] for detail in error["details"])
