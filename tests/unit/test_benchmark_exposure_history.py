import asyncio
from datetime import date

import pytest

from app.services.benchmark_exposure_history import (
    _build_benchmark_exposure_points,
    fetch_benchmark_exposure_history,
)
from tests.support.historical_attribution_fakes import RecordingHistoricalAttributionCoreClient


def test_build_benchmark_exposure_points_groups_by_sector_and_aggregates_weights() -> None:
    points = _build_benchmark_exposure_points(
        component_series=[
            {
                "index_id": "IDX_TECH_A",
                "points": [{"series_date": "2026-01-02", "component_weight": "0.30"}],
            },
            {
                "index_id": "IDX_TECH_B",
                "points": [{"series_date": "2026-01-02", "component_weight": "0.25"}],
            },
            {
                "index_id": "IDX_HEALTH",
                "points": [{"series_date": "2026-01-02", "component_weight": "0.45"}],
            },
        ],
        grouping_dimensions=["SECTOR"],
        index_classifications={
            "IDX_TECH_A": {"sector": "TECH"},
            "IDX_TECH_B": {"sector": "TECH"},
            "IDX_HEALTH": {"sector": "HEALTH"},
        },
    )

    weights_by_key = {point.group_key: point.weight for point in points}
    assert weights_by_key == {
        "SECTOR_TECH": 0.55,
        "SECTOR_HEALTH": 0.45,
    }


def test_fetch_benchmark_exposure_history_uses_decomposed_core_contracts() -> None:
    core = RecordingHistoricalAttributionCoreClient()

    points = asyncio.run(
        fetch_benchmark_exposure_history(
            core_client=core,
            portfolio_id="DEMO_DPM_EUR_001",
            as_of_date=date(2026, 1, 4),
            start_date=date(2026, 1, 2),
            reporting_currency="USD",
            grouping_dimensions=["SECTOR"],
            correlation_id="corr-benchmark-exposure",
        )
    )

    assert points
    assert core.assignment_calls[0]["request_payload"] == {"as_of_date": "2026-01-04"}
    assert core.index_catalog_calls[0]["correlation_id"] == "corr-benchmark-exposure"
    market_call = core.market_series_calls[0]
    assert market_call["benchmark_id"] == "BMK_GLOBAL_BALANCED_60_40"
    assert market_call["request_payload"] == {
        "as_of_date": "2026-01-04",
        "window": {"start_date": "2026-01-02", "end_date": "2026-01-04"},
        "frequency": "daily",
        "series_fields": ["component_weight"],
        "page": {"page_size": 5000, "page_token": None},
        "target_currency": "USD",
    }


def test_fetch_benchmark_exposure_history_rejects_issuer_grouping_until_semantics_exist() -> None:
    with pytest.raises(ValueError, match="cannot source benchmark exposure history"):
        asyncio.run(
            fetch_benchmark_exposure_history(
                core_client=RecordingHistoricalAttributionCoreClient(),
                portfolio_id="DEMO_DPM_EUR_001",
                as_of_date=date(2026, 1, 4),
                start_date=date(2026, 1, 2),
                reporting_currency=None,
                grouping_dimensions=["ISSUER"],
                correlation_id=None,
            )
        )


def test_fetch_benchmark_exposure_history_rejects_empty_benchmark_payload() -> None:
    class _EmptyBenchmarkCoreClient(RecordingHistoricalAttributionCoreClient):
        async def get_benchmark_market_series(
            self,
            *,
            benchmark_id: str,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            return {"component_series": [], "page": {"next_page_token": None}}

    with pytest.raises(ValueError, match="unable to build benchmark exposure history"):
        asyncio.run(
            fetch_benchmark_exposure_history(
                core_client=_EmptyBenchmarkCoreClient(),
                portfolio_id="DEMO_DPM_EUR_001",
                as_of_date=date(2026, 1, 4),
                start_date=date(2026, 1, 2),
                reporting_currency=None,
                grouping_dimensions=["SECTOR"],
                correlation_id=None,
            )
        )
