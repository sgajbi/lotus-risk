import asyncio
from datetime import date

import pytest

from app.contracts.attribution import GroupingDimension
from app.services.benchmark_exposure_history import (
    BENCHMARK_EXPOSURE_MAX_PAGES,
    BENCHMARK_EXPOSURE_MAX_ROWS,
    BENCHMARK_EXPOSURE_PAGE_SIZE,
    BenchmarkExposureHistoryRequest,
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


def _benchmark_request(
    performance: RecordingLotusPerformanceClient,
    *,
    reporting_currency: str | None = None,
    grouping_dimensions: list[GroupingDimension] | None = None,
    correlation_id: str | None = None,
) -> BenchmarkExposureHistoryRequest:
    return BenchmarkExposureHistoryRequest(
        performance_client=performance,
        portfolio_id="DEMO_DPM_EUR_001",
        as_of_date=date(2026, 1, 4),
        start_date=date(2026, 1, 2),
        reporting_currency=reporting_currency,
        grouping_dimensions=grouping_dimensions or ["SECTOR"],
        correlation_id=correlation_id,
    )


def _benchmark_rows(count: int) -> list[dict[str, object]]:
    return [
        {
            "valuation_date": "2026-01-02",
            "component_id": None,
            "grouping_dimension": "SECTOR",
            "group_key": f"SECTOR_{index}",
            "group_label": f"Sector {index}",
            "weight": "0.0001",
        }
        for index in range(count)
    ]


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
            _benchmark_request(
                performance,
                reporting_currency="USD",
                correlation_id="corr-benchmark-exposure",
            )
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
            _benchmark_request(performance, grouping_dimensions=["POSITION"])
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
            _benchmark_request(performance, correlation_id="corr-paged-benchmark")
        )
    )

    assert len(performance.benchmark_exposure_context_calls) == 2
    assert {call["correlation_id"] for call in performance.benchmark_exposure_context_calls} == {
        "corr-paged-benchmark"
    }
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
            _benchmark_request(performance, grouping_dimensions=["ISSUER"])
        )
    )

    assert points
    assert {point.grouping_dimension for point in points} == {"ISSUER"}
    assert performance.benchmark_exposure_context_calls[0]["request_payload"][
        "grouping_dimensions"
    ] == ["ISSUER"]


def test_fetch_benchmark_exposure_history_rejects_repeated_page_token() -> None:
    class _RepeatingTokenPerformanceClient(RecordingLotusPerformanceClient):
        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            self.benchmark_exposure_context_calls.append(
                {"request_payload": request_payload, "correlation_id": correlation_id}
            )
            payload = build_benchmark_exposure_context_response()
            return {**payload, "page": {"next_page_token": "same-token"}}

    performance = _RepeatingTokenPerformanceClient(
        response_payload=build_returns_series_response(portfolio_returns=[])
    )

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(
            fetch_benchmark_exposure_history(
                _benchmark_request(performance, correlation_id="corr-repeat")
            )
        )

    details = getattr(exc_info.value, "details")
    assert details["reason"] == "repeated_page_token"
    assert len(performance.benchmark_exposure_context_calls) == 2
    assert {call["correlation_id"] for call in performance.benchmark_exposure_context_calls} == {
        "corr-repeat"
    }


def test_fetch_benchmark_exposure_history_rejects_excessive_page_count() -> None:
    class _UnboundedPagesPerformanceClient(RecordingLotusPerformanceClient):
        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            self.benchmark_exposure_context_calls.append(
                {"request_payload": request_payload, "correlation_id": correlation_id}
            )
            token = f"page-{len(self.benchmark_exposure_context_calls) + 1}"
            return {
                **build_benchmark_exposure_context_response(),
                "rows": [],
                "page": {"next_page_token": token},
            }

    performance = _UnboundedPagesPerformanceClient(
        response_payload=build_returns_series_response(portfolio_returns=[])
    )

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))

    details = getattr(exc_info.value, "details")
    assert details["reason"] == "max_pages_exceeded"
    assert details["page_count"] == BENCHMARK_EXPOSURE_MAX_PAGES


def test_fetch_benchmark_exposure_history_rejects_excessive_row_count() -> None:
    class _OversizedRowsPerformanceClient(RecordingLotusPerformanceClient):
        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            self.benchmark_exposure_context_calls.append(
                {"request_payload": request_payload, "correlation_id": correlation_id}
            )
            token = f"page-{len(self.benchmark_exposure_context_calls) + 1}"
            return {
                **build_benchmark_exposure_context_response(),
                "rows": _benchmark_rows(BENCHMARK_EXPOSURE_PAGE_SIZE),
                "page": {"next_page_token": token},
            }

    performance = _OversizedRowsPerformanceClient(
        response_payload=build_returns_series_response(portfolio_returns=[])
    )

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))

    details = getattr(exc_info.value, "details")
    assert details["reason"] == "max_rows_exceeded"
    assert details["row_count"] == BENCHMARK_EXPOSURE_MAX_ROWS + BENCHMARK_EXPOSURE_PAGE_SIZE


def test_fetch_benchmark_exposure_history_rejects_empty_performance_payload() -> None:
    performance = _performance_client({**build_benchmark_exposure_context_response(), "rows": []})

    with pytest.raises(ValueError, match="unable to build benchmark exposure history"):
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))


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
                fetch_benchmark_exposure_history(_benchmark_request(_performance_client(payload)))
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
                _benchmark_request(_performance_client(), grouping_dimensions=["CUSTOM"])
            )
        )
