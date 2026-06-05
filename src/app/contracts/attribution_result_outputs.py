from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.contracts.attribution_inputs import (
    AttributionMetric,
    AttributionType,
    GroupingDimension,
)


class AttributionContributor(BaseModel):
    group_key: str = Field(
        description="Canonical contributor group key.",
        json_schema_extra={"example": "SECTOR_TECH"},
    )
    group_label: str | None = Field(
        default=None,
        description="Optional contributor display label.",
        json_schema_extra={"example": "Technology"},
    )
    weight_average: float | None = Field(
        default=None,
        description="Average group weight over attribution observation window.",
        json_schema_extra={"example": 0.245},
    )
    marginal_contribution: float | None = Field(
        default=None,
        description="Marginal contribution to risk in metric units.",
        json_schema_extra={"example": 0.0784},
    )
    component_contribution: float | None = Field(
        default=None,
        description="Component contribution to risk in metric units.",
        json_schema_extra={"example": 0.0192},
    )
    percent_contribution: float | None = Field(
        default=None,
        description="Percent contribution to total metric value.",
        json_schema_extra={"example": 0.1532},
    )


class AttributionSetResult(BaseModel):
    attribution_type: AttributionType = Field(
        description="Attribution decomposition type.",
        json_schema_extra={"example": "TOTAL_RISK"},
    )
    metric: AttributionMetric = Field(
        description="Attributed risk metric.",
        json_schema_extra={"example": "VOLATILITY"},
    )
    grouping_dimension: GroupingDimension = Field(
        description="Grouping dimension for contributors in this attribution set.",
        json_schema_extra={"example": "SECTOR"},
    )
    total_value: float | None = Field(  # monetary-float-allow: attribution metric value.
        default=None,
        description="Total metric value for this attribution set.",
        json_schema_extra={"example": 0.1253},
    )
    reconciled_sum: float | None = Field(
        default=None,
        description="Sum of component contributions used for reconciliation.",
        json_schema_extra={"example": 0.1249},
    )
    residual: float | None = Field(
        default=None,
        description="Residual reconciliation difference: total_value - reconciled_sum.",
        json_schema_extra={"example": 0.0004},
    )
    contributors: list[AttributionContributor] = Field(
        default_factory=list,
        description="Contributor decomposition rows for this attribution set.",
        json_schema_extra={
            "example": [
                {
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight_average": 0.245,
                    "marginal_contribution": 0.0784,
                    "component_contribution": 0.0192,
                    "percent_contribution": 0.1532,
                }
            ]
        },
    )
    quality_flags: list[str] = Field(
        default_factory=list,
        description="Deterministic quality flags for this attribution set.",
        json_schema_extra={"example": ["grouping:SECTOR:weight_not_sum_to_one"]},
    )


class HistoricalAttributionPeriodResult(BaseModel):
    start_date: dt.date = Field(
        description="Resolved period start date.",
        json_schema_extra={"example": "2026-01-01"},
    )
    end_date: dt.date = Field(
        description="Resolved period end date.",
        json_schema_extra={"example": "2026-02-28"},
    )
    attribution_sets: list[AttributionSetResult] = Field(
        default_factory=list,
        description="Attribution decomposition sets for the period.",
        json_schema_extra={
            "example": [
                {
                    "attribution_type": "TOTAL_RISK",
                    "metric": "VOLATILITY",
                    "grouping_dimension": "SECTOR",
                    "total_value": 0.1253,
                    "reconciled_sum": 0.1249,
                    "residual": 0.0004,
                    "contributors": [],
                    "quality_flags": [],
                }
            ]
        },
    )
    error: str | None = Field(
        default=None,
        description="Deterministic period-level error when attribution cannot be computed.",
        json_schema_extra={"example": "Insufficient data"},
    )


__all__ = [
    "AttributionContributor",
    "AttributionSetResult",
    "HistoricalAttributionPeriodResult",
]
