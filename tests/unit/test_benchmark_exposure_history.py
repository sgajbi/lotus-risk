import asyncio
from datetime import date

import pytest

from app.contracts.attribution import GroupingDimension
from app.contracts.downstream_authority import DownstreamAuthority
from app.services.benchmark_exposure_history import (
    BENCHMARK_EXPOSURE_MAX_PAGES,
    BENCHMARK_EXPOSURE_MAX_ROWS,
    BENCHMARK_EXPOSURE_PAGE_SIZE,
    BenchmarkExposureHistoryRequest,
    _rows_to_exposure_points,
    fetch_benchmark_exposure_history,
)
from app.upstream_errors import UpstreamServiceError
from tests.support.downstream_authority import admitted_test_authority
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
        as_of_date=date(2026, 1, 6),
        start_date=date(2026, 1, 2),
        reporting_currency=reporting_currency,
        grouping_dimensions=grouping_dimensions or ["SECTOR"],
        authority=admitted_test_authority(correlation_id),
    )


def _benchmark_rows(count: int, *, offset: int = 0) -> list[dict[str, object]]:
    return [
        {
            "valuation_date": "2026-01-02",
            "component_id": None,
            "grouping_dimension": "SECTOR",
            "group_key": f"SECTOR_{offset + index}",
            "group_label": f"Sector {index}",
            "weight": "0.0001",
        }
        for index in range(count)
    ]


def test_rows_to_exposure_points_parses_complete_performance_context_rows() -> None:
    points = _rows_to_exposure_points(
        [
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


@pytest.mark.parametrize(
    "bad_row",
    [
        "not-an-object",
        {"valuation_date": "2026-01-02", "grouping_dimension": "SECTOR", "weight": "0.1"},
        {
            "valuation_date": "2026-01-02",
            "grouping_dimension": "SECTOR",
            "group_key": "SECTOR_TECH",
            "weight": "NaN",
        },
        {
            "valuation_date": "2026-01-02",
            "grouping_dimension": "SECTOR",
            "group_key": "SECTOR_TECH",
            "weight": "0.1",
            "group_label": {"unexpected": "object"},
        },
        {
            "valuation_date": "2026-01-02",
            "grouping_dimension": "UNKNOWN_DIMENSION",
            "group_key": "SECTOR_TECH",
            "weight": "0.1",
        },
        {
            "valuation_date": "20260102",
            "grouping_dimension": "SECTOR",
            "group_key": "SECTOR_TECH",
            "weight": "0.1",
        },
        {
            "valuation_date": "not-a-date",
            "grouping_dimension": "SECTOR",
            "group_key": "SECTOR_TECH",
            "weight": "0.1",
        },
        {
            "valuation_date": "2026-01-02",
            "grouping_dimension": "SECTOR",
            "group_key": "SECTOR_TECH",
            "weight": "1e9999",
        },
    ],
)
def test_fetch_benchmark_exposure_history_refuses_partial_rows_even_when_source_says_complete(
    bad_row: object,
) -> None:
    payload = build_benchmark_exposure_context_response()
    rows = list(payload["rows"])
    rows[0] = bad_row
    performance = _performance_client({**payload, "rows": rows})

    with pytest.raises(UpstreamServiceError) as exc_info:
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"


@pytest.mark.parametrize(
    ("field_name", "wrong_value"),
    [
        ("portfolio_id", "FOREIGN_PORTFOLIO"),
        ("as_of_date", "2026-01-05"),
        ("window", {"start_date": "2026-01-03", "end_date": "2026-01-06"}),
        ("frequency", "MONTHLY"),
        ("reporting_currency", "USD"),
    ],
)
def test_fetch_benchmark_exposure_history_refuses_response_scope_mismatch(
    field_name: str, wrong_value: object
) -> None:
    payload = build_benchmark_exposure_context_response()
    performance = _performance_client({**payload, field_name: wrong_value})

    with pytest.raises(UpstreamServiceError, match=field_name) as exc_info:
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"


@pytest.mark.parametrize(
    ("field_name", "wrong_value"),
    [
        ("valuation_date", "2026-01-07"),
        ("grouping_dimension", "ISSUER"),
    ],
)
def test_fetch_benchmark_exposure_history_refuses_row_outside_requested_scope(
    field_name: str, wrong_value: str
) -> None:
    payload = build_benchmark_exposure_context_response()
    rows = list(payload["rows"])
    rows[0] = {**rows[0], field_name: wrong_value}
    performance = _performance_client({**payload, "rows": rows})

    with pytest.raises(UpstreamServiceError, match="outside requested scope") as exc_info:
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))

    assert exc_info.value.status_code == 502


def test_fetch_benchmark_exposure_history_uses_performance_context_contract() -> None:
    performance = _performance_client(
        {**build_benchmark_exposure_context_response(), "reporting_currency": "USD"}
    )

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
                "as_of_date": "2026-01-06",
                "window": {"start_date": "2026-01-02", "end_date": "2026-01-06"},
                "frequency": "DAILY",
                "grouping_dimensions": ["SECTOR"],
                "page": {"page_size": 1000, "page_token": None},
                "reporting_currency": "USD",
            },
            "tenant_id": "tenant-a",
            "correlation_id": "corr-benchmark-exposure",
        }
    ]


def test_fetch_benchmark_exposure_history_omits_currency_when_not_requested() -> None:
    performance = _performance_client()

    asyncio.run(
        fetch_benchmark_exposure_history(
            _benchmark_request(performance, grouping_dimensions=["SECTOR"])
        )
    )

    request_payload = performance.benchmark_exposure_context_calls[0]["request_payload"]
    assert "reporting_currency" not in request_payload
    assert request_payload["grouping_dimensions"] == ["SECTOR"]


def test_fetch_benchmark_exposure_history_follows_performance_pagination() -> None:
    class _PagedPerformanceClient(RecordingLotusPerformanceClient):
        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            self.benchmark_exposure_context_calls.append(
                {
                    "request_payload": request_payload,
                    "tenant_id": authority.tenant_id,
                    "correlation_id": authority.correlation_id,
                }
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


@pytest.mark.parametrize("second_page_mutation", ["duplicate_rows", "changed_benchmark"])
def test_fetch_benchmark_exposure_history_refuses_incoherent_pages(
    second_page_mutation: str,
) -> None:
    class _TwoPagePerformanceClient(RecordingLotusPerformanceClient):
        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            self.benchmark_exposure_context_calls.append(
                {"request_payload": request_payload, "tenant_id": authority.tenant_id}
            )
            payload = build_benchmark_exposure_context_response()
            rows = payload["rows"]
            if len(self.benchmark_exposure_context_calls) == 1:
                return {**payload, "rows": rows[:3], "page": {"next_page_token": "page-2"}}
            if second_page_mutation == "duplicate_rows":
                return {**payload, "rows": rows[:3], "page": {"next_page_token": None}}
            return {
                **payload,
                "benchmark_id": "OTHER_BENCHMARK",
                "rows": rows[3:],
                "page": {"next_page_token": None},
            }

    performance = _TwoPagePerformanceClient(
        response_payload=build_returns_series_response(portfolio_returns=[])
    )

    with pytest.raises(UpstreamServiceError) as exc_info:
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))

    assert exc_info.value.status_code == 502
    assert len(performance.benchmark_exposure_context_calls) == 2


@pytest.mark.parametrize("page", [None, {}, {"next_page_token": 7}, {"next_page_token": ""}])
def test_fetch_benchmark_exposure_history_refuses_malformed_pagination(page: object) -> None:
    payload = build_benchmark_exposure_context_response()
    performance = _performance_client({**payload, "page": page})

    with pytest.raises(UpstreamServiceError, match="pagination|next_page_token") as exc_info:
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))

    assert exc_info.value.status_code == 502


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
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            self.benchmark_exposure_context_calls.append(
                {
                    "request_payload": request_payload,
                    "tenant_id": authority.tenant_id,
                    "correlation_id": authority.correlation_id,
                }
            )
            payload = build_benchmark_exposure_context_response()
            return {**payload, "rows": [], "page": {"next_page_token": "same-token"}}

    performance = _RepeatingTokenPerformanceClient(
        response_payload=build_returns_series_response(portfolio_returns=[])
    )

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(
            fetch_benchmark_exposure_history(
                _benchmark_request(performance, correlation_id="corr-repeat")
            )
        )

    details = getattr(exc_info.value, "details")  # noqa: B009 - domain error extension
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
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            self.benchmark_exposure_context_calls.append(
                {
                    "request_payload": request_payload,
                    "tenant_id": authority.tenant_id,
                    "correlation_id": authority.correlation_id,
                }
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

    details = getattr(exc_info.value, "details")  # noqa: B009 - domain error extension
    assert details["reason"] == "max_pages_exceeded"
    assert details["page_count"] == BENCHMARK_EXPOSURE_MAX_PAGES


def test_fetch_benchmark_exposure_history_rejects_excessive_row_count() -> None:
    class _OversizedRowsPerformanceClient(RecordingLotusPerformanceClient):
        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            self.benchmark_exposure_context_calls.append(
                {
                    "request_payload": request_payload,
                    "tenant_id": authority.tenant_id,
                    "correlation_id": authority.correlation_id,
                }
            )
            token = f"page-{len(self.benchmark_exposure_context_calls) + 1}"
            return {
                **build_benchmark_exposure_context_response(),
                "rows": _benchmark_rows(
                    BENCHMARK_EXPOSURE_PAGE_SIZE,
                    offset=(len(self.benchmark_exposure_context_calls) - 1)
                    * BENCHMARK_EXPOSURE_PAGE_SIZE,
                ),
                "page": {"next_page_token": token},
            }

    performance = _OversizedRowsPerformanceClient(
        response_payload=build_returns_series_response(portfolio_returns=[])
    )

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))

    details = getattr(exc_info.value, "details")  # noqa: B009 - domain error extension
    assert details["reason"] == "max_rows_exceeded"
    assert details["row_count"] == BENCHMARK_EXPOSURE_MAX_ROWS + BENCHMARK_EXPOSURE_PAGE_SIZE


def test_fetch_benchmark_exposure_history_rejects_empty_performance_payload() -> None:
    performance = _performance_client({**build_benchmark_exposure_context_response(), "rows": []})

    with pytest.raises(ValueError, match="unable to build benchmark exposure history"):
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))


def test_fetch_benchmark_exposure_history_refuses_incomplete_source_economics() -> None:
    base_response = build_benchmark_exposure_context_response()
    metadata = dict(base_response["metadata"])
    metadata["exposure_source_quality"] = {
        "status": "incomplete",
        "omitted_component_count": 0,
        "omitted_point_count": 1,
        "reason_codes": ["MISSING_COMPONENT_WEIGHT"],
        "omissions": [
            {
                "component_id": "IDX_GLOBAL_BONDS",
                "series_date": "2026-01-02",
                "reason_code": "MISSING_COMPONENT_WEIGHT",
            }
        ],
        "omissions_truncated": False,
    }
    performance = _performance_client({**base_response, "metadata": metadata})

    with pytest.raises(
        UpstreamServiceError, match="incomplete economic source evidence"
    ) as exc_info:
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))

    assert exc_info.value.status_code == 424
    assert exc_info.value.code == "FAILED_DEPENDENCY"


@pytest.mark.parametrize(
    "source_quality",
    [
        None,
        {"status": "complete"},
        {"status": "unknown"},
        {
            "status": "complete",
            "omitted_component_count": 1,
            "omitted_point_count": 0,
            "reason_codes": [],
            "omissions": [],
            "omissions_truncated": False,
        },
        {
            "status": "complete",
            "omitted_component_count": 0,
            "omitted_point_count": 0,
            "reason_codes": ["MISSING_COMPONENT_WEIGHT"],
            "omissions": [],
            "omissions_truncated": False,
        },
    ],
)
def test_fetch_benchmark_exposure_history_refuses_malformed_complete_source_quality(
    source_quality: object,
) -> None:
    base_response = build_benchmark_exposure_context_response()
    metadata = dict(base_response["metadata"])
    metadata["exposure_source_quality"] = source_quality
    performance = _performance_client({**base_response, "metadata": metadata})

    with pytest.raises(UpstreamServiceError, match="exposure_source_quality") as exc_info:
        asyncio.run(fetch_benchmark_exposure_history(_benchmark_request(performance)))

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"


def test_fetch_benchmark_exposure_history_rejects_bad_performance_contract_shapes() -> None:
    base_response = build_benchmark_exposure_context_response()
    invalid_calculation_metadata = dict(base_response["metadata"])
    invalid_calculation_metadata["calculation_run_id"] = "22222222-2222-2222-2222-222222222222"
    invalid_contract_metadata = dict(base_response["metadata"])
    invalid_contract_metadata["contract_version"] = "v2"
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
        ({**base_response, "calculation_id": "not-a-uuid"}, "calculation lineage"),
        ({**base_response, "metadata": invalid_calculation_metadata}, "calculation lineage"),
        ({**base_response, "metadata": invalid_contract_metadata}, "metadata.contract_version=v1"),
        ({**base_response, "benchmark_id": ""}, "benchmark identity"),
    ]

    for payload, expected in cases:
        with pytest.raises(ValueError, match=expected):
            asyncio.run(
                fetch_benchmark_exposure_history(_benchmark_request(_performance_client(payload)))
            )

    malformed_id = {
        **base_response,
        "calculation_id": "not-a-uuid",
        "metadata": {**base_response["metadata"], "calculation_run_id": "not-a-uuid"},
    }
    with pytest.raises(UpstreamServiceError, match="invalid calculation lineage"):
        asyncio.run(
            fetch_benchmark_exposure_history(_benchmark_request(_performance_client(malformed_id)))
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
