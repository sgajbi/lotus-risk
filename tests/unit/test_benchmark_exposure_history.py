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


def test_build_benchmark_exposure_points_handles_position_grouping_and_skips_bad_rows() -> None:
    points = _build_benchmark_exposure_points(
        component_series=[
            "bad-component",  # type: ignore[list-item]
            {"points": [{"series_date": "2026-01-02", "component_weight": "0.10"}]},
            {"index_id": "IDX_IGNORED", "points": "bad-points"},
            {
                "index_id": "IDX_VALID",
                "points": [
                    "bad-point",
                    {"component_weight": "0.10"},
                    {"series_date": "2026-01-02"},
                    {"series_date": "2026-01-02", "component_weight": "0.40"},
                ],
            },
        ],
        grouping_dimensions=["POSITION"],
        index_classifications={},
    )

    assert [(point.group_key, point.group_label, point.weight) for point in points] == [
        ("IDX_VALID", "IDX_VALID", 0.4)
    ]


def test_build_benchmark_exposure_points_uses_unknown_labels_and_rejects_custom_grouping() -> None:
    points = _build_benchmark_exposure_points(
        component_series=[
            {
                "index_id": "IDX_UNCLASSIFIED",
                "points": [{"series_date": "2026-01-02", "component_weight": "0.40"}],
            }
        ],
        grouping_dimensions=["SECTOR", "ASSET_CLASS"],
        index_classifications={},
    )

    assert {point.group_key for point in points} == {"SECTOR_UNKNOWN", "ASSET_CLASS_UNKNOWN"}

    with pytest.raises(ValueError, match="only supports benchmark grouping_dimension"):
        _build_benchmark_exposure_points(
            component_series=[
                {
                    "index_id": "IDX_CUSTOM",
                    "points": [{"series_date": "2026-01-02", "component_weight": "0.40"}],
                }
            ],
            grouping_dimensions=["CUSTOM"],
            index_classifications={},
        )


def test_build_benchmark_exposure_points_rejects_invalid_weight() -> None:
    with pytest.raises(ValueError, match="Invalid benchmark exposure weight"):
        _build_benchmark_exposure_points(
            component_series=[
                {
                    "index_id": "IDX_BAD",
                    "points": [{"series_date": "2026-01-02", "component_weight": "bad"}],
                }
            ],
            grouping_dimensions=["POSITION"],
            index_classifications={},
        )


def test_fetch_benchmark_exposure_history_rejects_bad_core_contract_shapes() -> None:
    class _BadBenchmarkAssignmentClient(RecordingHistoricalAttributionCoreClient):
        async def resolve_benchmark_assignment(
            self,
            *,
            portfolio_id: str,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            return {"benchmark_id": None}

    class _BadIndexCatalogClient(RecordingHistoricalAttributionCoreClient):
        async def list_index_catalog(
            self,
            *,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            return {"records": "bad"}

    class _BadMarketSeriesClient(RecordingHistoricalAttributionCoreClient):
        async def get_benchmark_market_series(
            self,
            *,
            benchmark_id: str,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            return {"component_series": "bad"}

    base_request = {
        "portfolio_id": "DEMO_DPM_EUR_001",
        "as_of_date": date(2026, 1, 4),
        "start_date": date(2026, 1, 2),
        "reporting_currency": None,
        "grouping_dimensions": ["SECTOR"],
        "correlation_id": None,
    }

    with pytest.raises(ValueError, match="missing benchmark_id"):
        asyncio.run(
            fetch_benchmark_exposure_history(
                core_client=_BadBenchmarkAssignmentClient(),
                **base_request,  # type: ignore[arg-type]
            )
        )
    with pytest.raises(ValueError, match="index catalog payload missing"):
        asyncio.run(
            fetch_benchmark_exposure_history(
                core_client=_BadIndexCatalogClient(),
                **base_request,  # type: ignore[arg-type]
            )
        )
    with pytest.raises(ValueError, match="benchmark market-series payload missing"):
        asyncio.run(
            fetch_benchmark_exposure_history(
                core_client=_BadMarketSeriesClient(),
                **base_request,  # type: ignore[arg-type]
            )
        )


def test_fetch_benchmark_exposure_history_follows_market_series_pagination() -> None:
    class _PagedBenchmarkCoreClient(RecordingHistoricalAttributionCoreClient):
        async def get_benchmark_market_series(
            self,
            *,
            benchmark_id: str,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            self.market_series_calls.append(
                {
                    "benchmark_id": benchmark_id,
                    "request_payload": request_payload,
                    "correlation_id": correlation_id,
                }
            )
            page = request_payload.get("page")
            page_token = page.get("page_token") if isinstance(page, dict) else None
            if page_token is None:
                return {
                    "component_series": [],
                    "page": {"next_page_token": "page-2"},
                }
            return {
                "component_series": [
                    {
                        "index_id": "IDX_TECH",
                        "points": [{"series_date": "2026-01-02", "component_weight": "0.55"}],
                    }
                ],
                "page": {"next_page_token": None},
            }

    core = _PagedBenchmarkCoreClient()
    points = asyncio.run(
        fetch_benchmark_exposure_history(
            core_client=core,
            portfolio_id="DEMO_DPM_EUR_001",
            as_of_date=date(2026, 1, 4),
            start_date=date(2026, 1, 2),
            reporting_currency=None,
            grouping_dimensions=["SECTOR"],
            correlation_id=None,
        )
    )

    assert len(core.market_series_calls) == 2
    assert core.market_series_calls[1]["request_payload"]["page"]["page_token"] == "page-2"
    assert points[0].group_key == "SECTOR_TECH"
