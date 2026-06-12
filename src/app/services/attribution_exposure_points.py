from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.contracts.attribution import ExposurePoint, GroupingDimension


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


__all__ = ["as_decimal", "build_exposure_points", "group_key_and_label"]
