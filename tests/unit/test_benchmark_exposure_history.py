import asyncio
from datetime import date

import pytest

from app.services.benchmark_exposure_history import (
    _rows_to_exposure_points,
    fetch_benchmark_exposure_history,
)
from tests.support.historical_attribution_fakes import build_benchmark_exposure_context_response
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import build_returns_series_response


def _performance_client(
    payload: dict[str, object] | None = None,
) -> RecordingLotusPerformanceClient:
    return RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(portfolio_returns=[]),
        benchmark_exposure_context_payload=payload or build_benchmark_exposure_context_response(),
    )


def test_rows_to_exposure_points_parses_performance_context_rows_and_skips_bad_rows() -> None:
    points = _rows_to_exposure_points(
        [
            "bad-row",
            {"valuation_date": "2026-01-02", "grouping_dimension": "SECTOR", "weight": "0.1"},
            {
                "valuation_date": "2026-01-02",
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_TECH",
                "group_label": "Technology",
                "weight": "0.55",
            },
            {
                "valuation_date": "2026-01-02",
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_HEALTH",
                "group_label": "Healthcare",
                "weight": "0.45",
            },
        ]
    )

    assert [(point.group_key, point.group_label, point.weight) for point in points] == [
        ("SECTOR_HEALTH", "Healthcare", 0.45),
        ("SECTOR_TECH", "Technology", 0.55),
    ]


def test_fetch_benchmark_exposure_history_uses_performance_context_contract() -> None:
    performance = _performance_client()

    points = asyncio.run(
        fetch_benchmark_exposure_history(
            performance_client=performance,
            portfolio_id="DEMO_DPM_EUR_001",
            as_of_date=date(2026, 1, 4),
            start_date=date(2026, 1, 2),
            reporting_currency="USD",
            grouping_dimensions=["SECTOR"],
            correlation_id="corr-benchmark-exposure",
        )
    )

    assert points
    assert performance.benchmark_exposure_context_calls == [
        {
            "request_payload": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-04",
                "window": {"start_date": "2026-01-02", "end_date": "2026-01-04"},
                "frequency": "DAILY",
                "grouping_dimensions": ["SECTOR"],
                "page": {"page_size": 1000, "page_token": None},
                "reporting_currency": "USD",
            },
            "correlation_id": "corr-benchmark-exposure",
        }
    ]


def test_fetch_benchmark_exposure_history_omits_currency_when_not_requested() -> None:
    performance = _performance_client()

    asyncio.run(
        fetch_benchmark_exposure_history(
            performance_client=performance,
            portfolio_id="DEMO_DPM_EUR_001",
            as_of_date=date(2026, 1, 4),
            start_date=date(2026, 1, 2),
            reporting_currency=None,
            grouping_dimensions=["POSITION"],
            correlation_id=None,
        )
    )

    request_payload = performance.benchmark_exposure_context_calls[0]["request_payload"]
    assert "reporting_currency" not in request_payload
    assert request_payload["grouping_dimensions"] == ["POSITION"]


def test_fetch_benchmark_exposure_history_follows_performance_pagination() -> None:
    class _PagedPerformanceClient(RecordingLotusPerformanceClient):
        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            self.benchmark_exposure_context_calls.append(
                {"request_payload": request_payload, "correlation_id": correlation_id}
            )
            page = request_payload.get("page")
            page_token = page.get("page_token") if isinstance(page, dict) else None
            payload = build_benchmark_exposure_context_response()
            if page_token is None:
                return {**payload, "rows": [], "page": {"next_page_token": "page-2"}}
            return {**payload, "page": {"next_page_token": None}}

    performance = _PagedPerformanceClient(
        response_payload=build_returns_series_response(portfolio_returns=[])
    )

    points = asyncio.run(
        fetch_benchmark_exposure_history(
            performance_client=performance,
            portfolio_id="DEMO_DPM_EUR_001",
            as_of_date=date(2026, 1, 4),
            start_date=date(2026, 1, 2),
            reporting_currency=None,
            grouping_dimensions=["SECTOR"],
            correlation_id=None,
        )
    )

    assert len(performance.benchmark_exposure_context_calls) == 2
    assert (
        performance.benchmark_exposure_context_calls[1]["request_payload"]["page"]["page_token"]
        == "page-2"
    )
    assert points


def test_fetch_benchmark_exposure_history_accepts_issuer_grouping() -> None:
    performance = _performance_client(
        build_benchmark_exposure_context_response(grouping_dimension="ISSUER")
    )

    points = asyncio.run(
        fetch_benchmark_exposure_history(
            performance_client=performance,
            portfolio_id="DEMO_DPM_EUR_001",
            as_of_date=date(2026, 1, 4),
            start_date=date(2026, 1, 2),
            reporting_currency=None,
            grouping_dimensions=["ISSUER"],
            correlation_id=None,
        )
    )

    assert points
    assert {point.grouping_dimension for point in points} == {"ISSUER"}
    assert performance.benchmark_exposure_context_calls[0]["request_payload"][
        "grouping_dimensions"
    ] == ["ISSUER"]


def test_fetch_benchmark_exposure_history_rejects_empty_performance_payload() -> None:
    performance = _performance_client({**build_benchmark_exposure_context_response(), "rows": []})

    with pytest.raises(ValueError, match="unable to build benchmark exposure history"):
        asyncio.run(
            fetch_benchmark_exposure_history(
                performance_client=performance,
                portfolio_id="DEMO_DPM_EUR_001",
                as_of_date=date(2026, 1, 4),
                start_date=date(2026, 1, 2),
                reporting_currency=None,
                grouping_dimensions=["SECTOR"],
                correlation_id=None,
            )
        )


def test_fetch_benchmark_exposure_history_rejects_bad_performance_contract_shapes() -> None:
    base_response = build_benchmark_exposure_context_response()
    cases = [
        ({**base_response, "source_service": "lotus-core"}, "source_service=lotus-performance"),
        ({**base_response, "contract_version": "v2"}, "contract_version=v1"),
        ({**base_response, "metadata": "bad"}, "payload missing metadata object"),
        (
            {**base_response, "metadata": {"source_system": "lotus-performance"}},
            "lotus-core lineage",
        ),
        (
            {
                **base_response,
                "metadata": {"source_system": "lotus-core", "served_by": "lotus-core"},
            },
            "served_by=lotus-performance",
        ),
        ({**base_response, "rows": "bad"}, "payload missing 'rows' list"),
    ]

    for payload, expected in cases:
        with pytest.raises(ValueError, match=expected):
            asyncio.run(
                fetch_benchmark_exposure_history(
                    performance_client=_performance_client(payload),
                    portfolio_id="DEMO_DPM_EUR_001",
                    as_of_date=date(2026, 1, 4),
                    start_date=date(2026, 1, 2),
                    reporting_currency=None,
                    grouping_dimensions=["SECTOR"],
                    correlation_id=None,
                )
            )


def test_rows_to_exposure_points_rejects_invalid_weight() -> None:
    with pytest.raises(ValueError, match="Invalid benchmark exposure weight"):
        _rows_to_exposure_points(
            [
                {
                    "valuation_date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "weight": "bad",
                }
            ]
        )


def test_fetch_benchmark_exposure_history_rejects_custom_grouping() -> None:
    with pytest.raises(ValueError, match="cannot source benchmark exposure history"):
        asyncio.run(
            fetch_benchmark_exposure_history(
                performance_client=_performance_client(),
                portfolio_id="DEMO_DPM_EUR_001",
                as_of_date=date(2026, 1, 4),
                start_date=date(2026, 1, 2),
                reporting_currency=None,
                grouping_dimensions=["CUSTOM"],
                correlation_id=None,
            )
        )
