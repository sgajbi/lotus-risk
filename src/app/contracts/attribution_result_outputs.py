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
        description=(
            "Mean weight of this group over the observation window, as a decimal "
            "fraction of the portfolio (0.245 is 24.5%). For TOTAL_RISK this is the "
            "portfolio weight. For ACTIVE_RISK it is the ACTIVE weight, portfolio "
            "minus benchmark, so it is negative for an underweight. It is a weight, "
            "not a contribution: it does not carry metric units and is not derived "
            "from the return series. "
            "Averaged over the dates on which exposure was OBSERVED inside the "
            "window, not over every return date -- exposure history may be sparser "
            "than the return series, and a date with no observation is not a zero "
            "holding. Null when a group has no observed weight in the window at "
            "all. Zero is a zero AVERAGE and does not imply the group tracked the "
            "benchmark: a group overweight for part of the window and equally "
            "underweight later averages to zero having never matched it."
        ),
        json_schema_extra={"example": 0.245},
    )
    marginal_contribution: float | None = Field(
        default=None,
        description=(
            "The ratio `component_contribution / weight_average`, in metric units "
            "per unit of average weight. "
            "NOT a weight sensitivity, despite the name: `total_value` is computed "
            "from the portfolio return series alone and does not depend on the "
            "group weights, which only scale the contribution series after the "
            "total is fixed. So this does not answer what the metric would move by "
            "if the group's weight changed, and under constant weights it reports "
            "the same portfolio-level figure for every group rather than anything "
            "group-specific. Treating it as an actionable marginal will mislead. "
            "A genuine sensitivity needs per-group return series -- see "
            "lotus-risk#283. "
            "Null when `weight_average` is zero or unobserved; the row is still "
            "returned with its component."
        ),
        json_schema_extra={"example": 0.0784},
    )
    component_contribution: float | None = Field(
        default=None,
        description="Component contribution to risk in metric units.",
        json_schema_extra={"example": 0.0192},
    )
    percent_contribution: float | None = Field(
        default=None,
        description=(
            "Share of `total_value` attributable to this group: "
            "`component_contribution / total_value`. A DECIMAL RATIO despite the "
            "name -- 0.1532 means 15.32%. Multiply by 100 before rendering a "
            "percentage. May be negative where a group reduces the metric. "
            "Their sum across contributors is `reconciled_sum / total_value`, which "
            "is 1.0 only when `residual` is zero -- do not assume it, and do not "
            "normalise to it. Under TOTAL_RISK it approaches 1.0 as the residual "
            "approaches zero. Under ACTIVE_RISK it approaches ZERO for fully "
            "allocated histories, because the values then carry active weights that "
            "sum to zero. A consumer validating `sum == 1` will reject valid "
            "responses. See lotus-risk#283."
        ),
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
        description=(
            "The metric being decomposed, for the whole set: annualised volatility "
            "for VOLATILITY, annualised tracking error for TRACKING_ERROR. A decimal "
            "ratio (0.1253 is 12.53%), annualised at `metadata.annualization_basis`. "
            "Null when the period could not be computed; see `error`."
        ),
        json_schema_extra={"example": 0.1253},
    )
    reconciled_sum: float | None = Field(
        default=None,
        description=(
            "Sum of `component_contribution` across EVERY contributor in this set. "
            "Contributors are never a top-N subset, so this is the full sum and not "
            "a remainder-bearing figure."
        ),
        json_schema_extra={"example": 0.1249},
    )
    residual: float | None = Field(
        default=None,
        description=(
            "`total_value - reconciled_sum`, in the same units as `total_value`. The "
            "part of the metric the decomposition did not attribute to any group. "
            "Present it; do not allocate it away across contributors -- a residual "
            "spread over groups is indistinguishable from attribution the service "
            "actually made. "
            "Under TOTAL_RISK the residual is near zero when weights sum to one; a "
            "larger one is reported as `grouping:<dim>:weight_not_sum_to_one` in "
            "`quality_flags`. Note that flag is advisory -- a set whose weights do "
            "not sum to one is still computed and returned. "
            "Under ACTIVE_RISK, for FULLY ALLOCATED portfolio and benchmark "
            "histories, the residual is the whole metric: active weights then sum "
            "to zero, so the components do too and nothing is attributed. Where "
            "either history is not fully allocated the active weights sum to the "
            "difference and the residual is correspondingly smaller, which is not a "
            "better decomposition -- only a less obvious one. See lotus-risk#283 "
            "before presenting an active-risk decomposition."
        ),
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
