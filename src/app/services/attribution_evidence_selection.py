"""Select joinable producer evidence without expanding Risk's grouping contract."""

from __future__ import annotations

from datetime import date

from app.contracts.attribution import (
    AttributionMetric,
    AttributionType,
    GroupingDimension,
    HistoricalAttributionStatefulInput,
)
from app.contracts.risk import ReturnPoint
from app.services.attribution_group_evidence import (
    EMPIRICAL_GROUPING_DIMENSION_FIELDS,
)


def evidence_grouping_dimensions(
    options_grouping_dimensions: list[GroupingDimension],
    attribution_types: list[AttributionType],
    metrics: list[AttributionMetric],
) -> list[GroupingDimension]:
    """Only dimensions with an exact producer-to-Risk group identity join."""
    needs_total = "TOTAL_RISK" in attribution_types and "VOLATILITY" in metrics
    needs_active = "ACTIVE_RISK" in attribution_types and "TRACKING_ERROR" in metrics
    if not needs_total and not needs_active:
        return []
    return [
        dimension
        for dimension in options_grouping_dimensions
        if dimension in EMPIRICAL_GROUPING_DIMENSION_FIELDS
    ]


def active_evidence_available(
    stateful: HistoricalAttributionStatefulInput,
    dimension: GroupingDimension,
    needs_active: bool,
) -> bool:
    """The producer's v1 economics cannot substitute for NET or an unknown currency."""
    return (
        needs_active
        and dimension in {"SECTOR", "ASSET_CLASS"}
        and stateful.net_or_gross == "GROSS"
        and stateful.reporting_currency is not None
    )


def total_evidence_available(dimension: GroupingDimension, needs_total: bool) -> bool:
    return needs_total and dimension in EMPIRICAL_GROUPING_DIMENSION_FIELDS


def window_return_points(
    points: list[ReturnPoint],
    start_date: date,
    end_date: date,
) -> list[ReturnPoint]:
    return [point for point in points if start_date <= point.date <= end_date]
