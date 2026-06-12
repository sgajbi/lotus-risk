from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from app.contracts.attribution import (
    GroupingDimension,
    HistoricalAttributionStatefulInput,
)
from app.contracts.attribution import ExposurePoint
from app.services.attribution_exposure_points import (
    as_decimal,
    build_exposure_points,
    group_key_and_label,
)
from app.services.attribution_position_timeseries import (
    LotusCorePositionTimeseriesClient,
    fetch_position_timeseries_rows,
)
from app.upstream_errors import invalid_upstream_payload, missing_upstream_data


__all__ = [
    "LotusCoreClientProtocol",
    "as_decimal",
    "build_exposure_points",
    "build_issuer_map",
    "fetch_stateful_exposure_history",
    "group_key_and_label",
]


class LotusCoreClientProtocol(LotusCorePositionTimeseriesClient, Protocol):
    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


def _security_ids_from_position_rows(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("security_id"))
            for row in rows
            if isinstance(row, dict) and row.get("security_id")
        }
    )


def _issuer_identity_from_record(
    record: dict[str, Any],
) -> tuple[str, tuple[str, str | None]] | None:
    security_id_raw = record.get("security_id")
    if not security_id_raw:
        return None
    security_id = str(security_id_raw)
    issuer_id_raw = record.get("issuer_id")
    issuer_name_raw = record.get("issuer_name")
    issuer_id = str(issuer_id_raw) if issuer_id_raw else f"ISSUER_{security_id}"
    issuer_name = str(issuer_name_raw) if issuer_name_raw else None
    return security_id, (issuer_id, issuer_name)


async def build_issuer_map(
    *,
    core_client: LotusCoreClientProtocol,
    rows: list[dict[str, Any]],
    correlation_id: str | None,
) -> dict[str, tuple[str, str | None]]:
    security_ids = _security_ids_from_position_rows(rows)
    if not security_ids:
        return {}
    response = await core_client.get_instrument_enrichment(
        security_ids=security_ids,
        correlation_id=correlation_id,
    )
    records = response.get("records")
    if not isinstance(records, list):
        raise invalid_upstream_payload(
            service="lotus-core",
            operation="/integration/instruments/enrichment-bulk",
            message="lotus-core enrichment payload missing 'records' list",
        )
    issuer_map: dict[str, tuple[str, str | None]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        issuer_identity = _issuer_identity_from_record(record)
        if issuer_identity is not None:
            security_id, issuer = issuer_identity
            issuer_map[security_id] = issuer
    return issuer_map


def _position_timeseries_operation(portfolio_id: str) -> str:
    return f"/integration/portfolios/{portfolio_id}/analytics/position-timeseries"


def _require_position_timeseries_rows(
    *,
    rows: list[dict[str, Any]],
    portfolio_id: str,
) -> None:
    if not rows:
        raise missing_upstream_data(
            service="lotus-core",
            operation=_position_timeseries_operation(portfolio_id),
            message="lotus-core position-timeseries returned no rows",
        )


async def _issuer_map_for_grouping_dimensions(
    *,
    core_client: LotusCoreClientProtocol,
    rows: list[dict[str, Any]],
    grouping_dimensions: list[GroupingDimension],
    correlation_id: str | None,
) -> dict[str, tuple[str, str | None]]:
    if "ISSUER" not in grouping_dimensions:
        return {}
    return await build_issuer_map(
        core_client=core_client,
        rows=rows,
        correlation_id=correlation_id,
    )


def _validated_exposure_history(
    *,
    rows: list[dict[str, Any]],
    grouping_dimensions: list[GroupingDimension],
    issuer_map: dict[str, tuple[str, str | None]],
    portfolio_id: str,
) -> list[ExposurePoint]:
    exposure_history = build_exposure_points(
        rows=rows,
        grouping_dimensions=grouping_dimensions,
        issuer_map=issuer_map,
    )
    if not exposure_history:
        raise missing_upstream_data(
            service="lotus-core",
            operation=_position_timeseries_operation(portfolio_id),
            message="unable to build exposure history from lotus-core position-timeseries",
        )
    return exposure_history


async def fetch_stateful_exposure_history(
    *,
    stateful: HistoricalAttributionStatefulInput,
    core_client: LotusCoreClientProtocol,
    start_date: date,
    grouping_dimensions: list[GroupingDimension],
    correlation_id: str | None,
) -> list[ExposurePoint]:
    rows = await fetch_position_timeseries_rows(
        core_client=core_client,
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        start_date=start_date,
        reporting_currency=stateful.reporting_currency,
        grouping_dimensions=grouping_dimensions,
        correlation_id=correlation_id,
    )
    _require_position_timeseries_rows(rows=rows, portfolio_id=stateful.portfolio_id)
    issuer_map = await _issuer_map_for_grouping_dimensions(
        core_client=core_client,
        rows=rows,
        grouping_dimensions=grouping_dimensions,
        correlation_id=correlation_id,
    )
    return _validated_exposure_history(
        rows=rows,
        grouping_dimensions=grouping_dimensions,
        issuer_map=issuer_map,
        portfolio_id=stateful.portfolio_id,
    )
