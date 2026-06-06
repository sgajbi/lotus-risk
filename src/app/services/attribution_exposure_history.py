from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.contracts.attribution import (
    ExposurePoint,
    GroupingDimension,
    HistoricalAttributionStatefulInput,
)
from app.services.attribution_position_timeseries import (
    LotusCorePositionTimeseriesClient,
    fetch_position_timeseries_rows,
)
from app.upstream_errors import invalid_upstream_payload, missing_upstream_data


class LotusCoreClientProtocol(LotusCorePositionTimeseriesClient, Protocol):
    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


def group_key_and_label(
    *,
    row: dict[str, Any],
    grouping_dimension: GroupingDimension,
    issuer_map: dict[str, tuple[str, str | None]],
) -> tuple[str, str | None]:
    security_id_raw = row.get("security_id")
    security_id = str(security_id_raw) if security_id_raw else "UNKNOWN_SECURITY"
    dimensions_raw = row.get("dimensions")
    dimensions = dimensions_raw if isinstance(dimensions_raw, dict) else {}

    if grouping_dimension == "POSITION":
        return security_id, security_id
    if grouping_dimension == "SECTOR":
        sector = dimensions.get("sector")
        label = str(sector) if sector else "UNKNOWN"
        return f"SECTOR_{label}", label
    if grouping_dimension == "ASSET_CLASS":
        asset_class = dimensions.get("asset_class")
        label = str(asset_class) if asset_class else "UNKNOWN"
        return f"ASSET_CLASS_{label}", label
    if grouping_dimension == "ISSUER":
        issuer_id, issuer_name = issuer_map.get(security_id, (f"ISSUER_{security_id}", None))
        return issuer_id, issuer_name
    raise ValueError(f"Unsupported stateful grouping_dimension={grouping_dimension}")


def as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"Invalid market value from lotus-core position-timeseries: {value}"
        ) from exc


@dataclass
class _ExposureAggregation:
    grouped_values: dict[tuple[date, GroupingDimension, str], Decimal] = field(default_factory=dict)
    totals_by_date: dict[date, Decimal] = field(default_factory=dict)
    labels: dict[tuple[GroupingDimension, str], str | None] = field(default_factory=dict)

    def add_row(
        self,
        *,
        row: dict[str, Any],
        obs_date: date,
        market_value: Decimal,
        grouping_dimensions: list[GroupingDimension],
        issuer_map: dict[str, tuple[str, str | None]],
    ) -> None:
        self.totals_by_date[obs_date] = (
            self.totals_by_date.get(obs_date, Decimal("0")) + market_value
        )
        for grouping_dimension in grouping_dimensions:
            group_key, group_label = group_key_and_label(
                row=row,
                grouping_dimension=grouping_dimension,
                issuer_map=issuer_map,
            )
            self.labels[(grouping_dimension, group_key)] = group_label
            key = (obs_date, grouping_dimension, group_key)
            self.grouped_values[key] = self.grouped_values.get(key, Decimal("0")) + market_value


def _market_value_from_position_row(row: dict[str, Any]) -> Decimal:
    ending_reporting = row.get("ending_market_value_reporting_currency")
    ending_portfolio = row.get("ending_market_value_portfolio_currency")
    return as_decimal(ending_reporting if ending_reporting is not None else ending_portfolio)


def _exposure_points_from_aggregation(
    aggregation: _ExposureAggregation,
) -> list[ExposurePoint]:
    points: list[ExposurePoint] = []
    for (obs_date, grouping_dimension, group_key), numerator in aggregation.grouped_values.items():
        denominator = aggregation.totals_by_date.get(obs_date, Decimal("0"))
        if denominator == 0:
            continue
        points.append(
            ExposurePoint(
                date=obs_date,
                grouping_dimension=grouping_dimension,
                group_key=group_key,
                group_label=aggregation.labels.get((grouping_dimension, group_key)),
                weight=float(numerator / denominator),
            )
        )
    points.sort(key=lambda item: (item.date, item.grouping_dimension, item.group_key))
    return points


def build_exposure_points(
    *,
    rows: list[dict[str, Any]],
    grouping_dimensions: list[GroupingDimension],
    issuer_map: dict[str, tuple[str, str | None]],
) -> list[ExposurePoint]:
    aggregation = _ExposureAggregation()
    for row in rows:
        valuation_date = row.get("valuation_date")
        if not isinstance(valuation_date, str):
            continue
        aggregation.add_row(
            row=row,
            obs_date=date.fromisoformat(valuation_date),
            market_value=_market_value_from_position_row(row),
            grouping_dimensions=grouping_dimensions,
            issuer_map=issuer_map,
        )
    return _exposure_points_from_aggregation(aggregation)


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
