from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.risk import RiskRequestPeriod


class AttributionInputMode(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"


AttributionType = Literal["TOTAL_RISK", "ACTIVE_RISK"]
AttributionMetric = Literal["VOLATILITY", "TRACKING_ERROR"]

AttributionValueUnit = Literal["decimal_ratio", "unitless"]

#: Source-owned unit semantics per attributed metric, covering total_value,
#: reconciled_sum, residual, and marginal/component contributions ("metric
#: units"). decimal_ratio values are decimal fractions of one (0.1253 means
#: 12.53%). weight_average and percent_contribution are ALWAYS decimal
#: fractions of one by field contract and are not repeated here. Every
#: AttributionMetric MUST have an entry: an attributed value without stated
#: unit semantics is unreadable downstream.
ATTRIBUTION_METRIC_UNIT_SEMANTICS: dict[str, AttributionValueUnit] = {
    "VOLATILITY": "decimal_ratio",
    "TRACKING_ERROR": "decimal_ratio",
}
GroupingDimension = Literal["POSITION", "ISSUER", "SECTOR", "ASSET_CLASS", "CUSTOM"]


def _default_attribution_types() -> list[AttributionType]:
    return ["TOTAL_RISK"]


def _default_metrics() -> list[AttributionMetric]:
    return ["VOLATILITY"]


def _default_groupings() -> list[GroupingDimension]:
    return ["POSITION"]


def validate_unique_period_names(periods: list[RiskRequestPeriod]) -> None:
    resolved_names = [period.name or period.type for period in periods]
    duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
    if duplicates:
        raise ValueError(
            "Duplicate period names resolved in request: "
            + ", ".join(duplicates)
            + ". Each period name (or type fallback) must be unique."
        )


class AttributionOptions(BaseModel):
    attribution_types: list[AttributionType] = Field(
        default_factory=_default_attribution_types,
        description="Requested attribution decomposition types.",
        json_schema_extra={"example": ["TOTAL_RISK", "ACTIVE_RISK"]},
    )
    metrics: list[AttributionMetric] = Field(
        default_factory=_default_metrics,
        description="Requested risk metrics for attribution decomposition.",
        json_schema_extra={"example": ["VOLATILITY", "TRACKING_ERROR"]},
    )
    grouping_dimensions: list[GroupingDimension] = Field(
        default_factory=_default_groupings,
        description="Requested grouping dimensions for contributor decomposition.",
        json_schema_extra={"example": ["POSITION", "ISSUER", "SECTOR"]},
    )
    annualization_basis: int = Field(
        default=252,
        ge=1,
        description="Annualization basis used for volatility and tracking-error attribution.",
        json_schema_extra={"example": 252},
    )
    covariance_method: Literal["EMPIRICAL"] = Field(
        default="EMPIRICAL",
        description="Covariance estimator used for component contribution calculations.",
        json_schema_extra={"example": "EMPIRICAL"},
    )
    min_observations_policy: Literal["STRICT", "ALLOW_PARTIAL"] = Field(
        default="STRICT",
        description="Minimum observation policy used for period-level attribution.",
        json_schema_extra={"example": "STRICT"},
    )

    @model_validator(mode="after")
    def validate_lists(self) -> AttributionOptions:
        if not self.attribution_types:
            raise ValueError("attribution_types must include at least one value")
        if not self.metrics:
            raise ValueError("metrics must include at least one value")
        if not self.grouping_dimensions:
            raise ValueError("grouping_dimensions must include at least one value")
        return self


class ExposurePoint(BaseModel):
    date: dt.date = Field(
        description="Date of exposure observation.",
        json_schema_extra={"example": "2026-01-02"},
    )
    grouping_dimension: GroupingDimension = Field(
        description="Grouping dimension used for this exposure row.",
        json_schema_extra={"example": "SECTOR"},
    )
    group_key: str = Field(
        description="Canonical group key for the contributor bucket.",
        json_schema_extra={"example": "SECTOR_TECH"},
    )
    group_label: str | None = Field(
        default=None,
        description="Optional display label for contributor bucket.",
        json_schema_extra={"example": "Technology"},
    )
    weight: float = Field(
        description="Portfolio or benchmark weight in decimal units for this group/date.",
        json_schema_extra={"example": 0.245},
    )


def requires_active_attribution(options: AttributionOptions) -> bool:
    return "ACTIVE_RISK" in options.attribution_types or "TRACKING_ERROR" in options.metrics


__all__ = [
    "AttributionInputMode",
    "AttributionMetric",
    "AttributionOptions",
    "AttributionType",
    "ExposurePoint",
    "GroupingDimension",
    "requires_active_attribution",
    "validate_unique_period_names",
]
