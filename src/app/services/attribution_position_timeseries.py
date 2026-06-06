from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from app.contracts.attribution import GroupingDimension
from app.upstream_errors import invalid_upstream_payload


class LotusCorePositionTimeseriesClient(Protocol):
    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


def position_timeseries_dimensions(grouping_dimensions: list[GroupingDimension]) -> list[str]:
    dimensions: list[str] = []
    if "SECTOR" in grouping_dimensions:
        dimensions.append("sector")
    if "ASSET_CLASS" in grouping_dimensions:
        dimensions.append("asset_class")
    return dimensions


async def fetch_position_timeseries_rows(
    *,
    core_client: LotusCorePositionTimeseriesClient,
    portfolio_id: str,
    as_of_date: date,
    start_date: date,
    reporting_currency: str | None,
    grouping_dimensions: list[GroupingDimension],
    correlation_id: str | None,
) -> list[dict[str, Any]]:
    dimensions = position_timeseries_dimensions(grouping_dimensions)
    page_token: str | None = None
    rows: list[dict[str, Any]] = []
    while True:
        response = await core_client.get_position_analytics_timeseries(
            portfolio_id=portfolio_id,
            request_payload=_position_timeseries_payload(
                as_of_date=as_of_date,
                start_date=start_date,
                reporting_currency=reporting_currency,
                dimensions=dimensions,
                page_token=page_token,
            ),
            correlation_id=correlation_id,
        )
        rows.extend(_extract_position_rows_batch(response=response, portfolio_id=portfolio_id))
        page_token = _next_position_page_token(response)
        if page_token is None:
            break
    return rows


def _position_timeseries_payload(
    *,
    as_of_date: date,
    start_date: date,
    reporting_currency: str | None,
    dimensions: list[str],
    page_token: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "as_of_date": as_of_date.isoformat(),
        "window": {
            "start_date": start_date.isoformat(),
            "end_date": as_of_date.isoformat(),
        },
        "frequency": "daily",
        "dimensions": dimensions,
        "consumer_system": "lotus-risk",
        "page": {"page_size": 5000, "page_token": page_token},
    }
    if reporting_currency:
        payload["reporting_currency"] = reporting_currency
    return payload


def _extract_position_rows_batch(
    *,
    response: dict[str, Any],
    portfolio_id: str,
) -> list[dict[str, Any]]:
    batch = response.get("rows")
    if not isinstance(batch, list):
        raise invalid_upstream_payload(
            service="lotus-core",
            operation=f"/integration/portfolios/{portfolio_id}/analytics/position-timeseries",
            message="lotus-core position-timeseries payload missing 'rows' list",
        )
    return [row for row in batch if isinstance(row, dict)]


def _next_position_page_token(response: dict[str, Any]) -> str | None:
    page = response.get("page")
    next_page_token = page.get("next_page_token") if isinstance(page, dict) else None
    return next_page_token if isinstance(next_page_token, str) and next_page_token else None
