import asyncio
from datetime import date
from typing import Any

import pytest

from app.services.attribution_position_timeseries import (
    POSITION_TIMESERIES_MAX_PAGES,
    POSITION_TIMESERIES_MAX_ROWS,
    POSITION_TIMESERIES_PAGE_SIZE,
    fetch_position_timeseries_rows,
)


def _position_row(index: int) -> dict[str, object]:
    return {
        "security_id": f"SEC_{index}",
        "valuation_date": "2026-01-02",
        "dimensions": {"sector": "TECH", "asset_class": "EQUITY"},
        "ending_market_value_portfolio_currency": "100",
    }


class _PagedCoreClient:
    def __init__(self, pages: list[dict[str, object]]) -> None:
        self.pages = pages
        self.position_calls: list[dict[str, Any]] = []

    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, object]:
        self.position_calls.append(
            {
                "portfolio_id": portfolio_id,
                "request_payload": request_payload,
                "correlation_id": correlation_id,
            }
        )
        index = len(self.position_calls) - 1
        return self.pages[min(index, len(self.pages) - 1)]


def _fetch_rows(client: _PagedCoreClient) -> list[dict[str, Any]]:
    return asyncio.run(
        fetch_position_timeseries_rows(
            core_client=client,
            portfolio_id="PB_SG_GLOBAL_BAL_001",
            as_of_date=date(2026, 1, 6),
            start_date=date(2026, 1, 2),
            reporting_currency="USD",
            grouping_dimensions=["SECTOR", "ASSET_CLASS"],
            correlation_id="corr-position-pages",
        )
    )


def test_fetch_position_timeseries_rows_follows_pagination_and_correlation() -> None:
    client = _PagedCoreClient(
        [
            {"rows": [_position_row(1)], "page": {"next_page_token": "page-2"}},
            {"rows": [_position_row(2)], "page": {"next_page_token": None}},
        ]
    )

    rows = _fetch_rows(client)

    assert [row["security_id"] for row in rows] == ["SEC_1", "SEC_2"]
    assert len(client.position_calls) == 2
    assert {call["correlation_id"] for call in client.position_calls} == {"corr-position-pages"}
    first_payload = client.position_calls[0]["request_payload"]
    second_payload = client.position_calls[1]["request_payload"]
    assert first_payload["page"] == {
        "page_size": POSITION_TIMESERIES_PAGE_SIZE,
        "page_token": None,
    }
    assert second_payload["page"] == {
        "page_size": POSITION_TIMESERIES_PAGE_SIZE,
        "page_token": "page-2",
    }
    assert first_payload["dimensions"] == ["sector", "asset_class"]
    assert first_payload["reporting_currency"] == "USD"


def test_fetch_position_timeseries_rows_rejects_repeated_page_token() -> None:
    client = _PagedCoreClient(
        [
            {"rows": [_position_row(1)], "page": {"next_page_token": "same-token"}},
        ]
    )

    with pytest.raises(ValueError) as exc_info:
        _fetch_rows(client)

    details = getattr(exc_info.value, "details")  # noqa: B009 - domain error extension
    assert details["service"] == "lotus-core"
    assert details["operation"] == (
        "/integration/portfolios/PB_SG_GLOBAL_BAL_001/analytics/position-timeseries"
    )
    assert details["reason"] == "repeated_page_token"
    assert details["page_count"] == 2
    assert len(client.position_calls) == 2


def test_fetch_position_timeseries_rows_rejects_excessive_page_count() -> None:
    client = _PagedCoreClient(
        [
            {
                "rows": [],
                "page": {"next_page_token": f"page-{index}"},
            }
            for index in range(2, POSITION_TIMESERIES_MAX_PAGES + 2)
        ]
    )

    with pytest.raises(ValueError) as exc_info:
        _fetch_rows(client)

    details = getattr(exc_info.value, "details")  # noqa: B009 - domain error extension
    assert details["reason"] == "max_pages_exceeded"
    assert details["page_count"] == POSITION_TIMESERIES_MAX_PAGES


def test_fetch_position_timeseries_rows_rejects_excessive_row_count() -> None:
    oversized_page = [_position_row(index) for index in range(POSITION_TIMESERIES_MAX_ROWS + 1)]
    client = _PagedCoreClient(
        [
            {
                "rows": oversized_page,
                "page": {"next_page_token": None},
            }
        ]
    )

    with pytest.raises(ValueError) as exc_info:
        _fetch_rows(client)

    details = getattr(exc_info.value, "details")  # noqa: B009 - domain error extension
    assert details["reason"] == "max_rows_exceeded"
    assert details["row_count"] == POSITION_TIMESERIES_MAX_ROWS + 1
