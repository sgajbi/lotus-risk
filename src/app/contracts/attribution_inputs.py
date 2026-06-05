from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.attribution_examples import HISTORICAL_ATTRIBUTION_REQUEST_EXAMPLE
from app.contracts.risk import ReturnPoint, RiskRequestPeriod, RiskRequestScope


class AttributionInputMode(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"


AttributionType = Literal["TOTAL_RISK", "ACTIVE_RISK"]
AttributionMetric = Literal["VOLATILITY", "TRACKING_ERROR"]
GroupingDimension = Literal["POSITION", "ISSUER", "SECTOR", "ASSET_CLASS", "CUSTOM"]


def _default_attribution_types() -> list[AttributionType]:
    return ["TOTAL_RISK"]


def _default_metrics() -> list[AttributionMetric]:
    return ["VOLATILITY"]


def _default_groupings() -> list[GroupingDimension]:
    return ["POSITION"]


def _validate_unique_period_names(periods: list[RiskRequestPeriod]) -> None:
    resolved_names = [period.name or period.type for period in periods]
    duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
    if duplicates:
        raise ValueError(
            "Duplicate period names resolved in request: "
            + ", ".join(duplicates)
            + ". Each period name (or type fallback) must be unique."
        )


def _requires_active_attribution(options: "AttributionOptions") -> bool:
    return "ACTIVE_RISK" in options.attribution_types or "TRACKING_ERROR" in options.metrics


def _validate_active_attribution_inputs(
    *,
    attribution_options: "AttributionOptions",
    benchmark_returns: list[ReturnPoint],
    benchmark_exposure_history: list["ExposurePoint"],
) -> None:
    if not _requires_active_attribution(attribution_options):
        return
    if not benchmark_returns:
        raise ValueError(
            "benchmark_returns are required when requesting ACTIVE_RISK or TRACKING_ERROR attribution"
        )
    if not benchmark_exposure_history:
        raise ValueError(
            "benchmark_exposure_history are required when requesting ACTIVE_RISK or TRACKING_ERROR attribution"
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
    def validate_lists(self) -> "AttributionOptions":
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


class HistoricalAttributionStatelessInput(BaseModel):
    scope: RiskRequestScope = Field(
        description="Scope and policy context for historical attribution calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    periods: list[RiskRequestPeriod] = Field(
        description="List of periods to evaluate historical attribution.",
        json_schema_extra={"example": [{"type": "YTD", "name": "YTD"}]},
    )
    returns: list[ReturnPoint] = Field(
        description="Portfolio return observations in percentage points.",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.62}]},
    )
    benchmark_returns: list[ReturnPoint] = Field(
        default_factory=list,
        description="Benchmark return observations in percentage points (required for active attribution).",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.51}]},
    )
    exposure_history: list[ExposurePoint] = Field(
        description="Portfolio exposure history grouped by requested dimensions.",
        json_schema_extra={
            "example": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.245,
                }
            ]
        },
    )
    benchmark_exposure_history: list[ExposurePoint] = Field(
        default_factory=list,
        description="Benchmark exposure history for active-risk attribution decomposition.",
        json_schema_extra={
            "example": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.210,
                }
            ]
        },
    )
    attribution_options: AttributionOptions = Field(
        default_factory=AttributionOptions,
        description="Historical attribution calculation options.",
        json_schema_extra={
            "example": {
                "attribution_types": ["TOTAL_RISK", "ACTIVE_RISK"],
                "metrics": ["VOLATILITY", "TRACKING_ERROR"],
                "grouping_dimensions": ["POSITION", "SECTOR"],
                "annualization_basis": 252,
                "covariance_method": "EMPIRICAL",
                "min_observations_policy": "STRICT",
            }
        },
    )

    @model_validator(mode="after")
    def validate_semantics(self) -> "HistoricalAttributionStatelessInput":
        _validate_unique_period_names(self.periods)
        _validate_active_attribution_inputs(
            attribution_options=self.attribution_options,
            benchmark_returns=self.benchmark_returns,
            benchmark_exposure_history=self.benchmark_exposure_history,
        )
        return self


class HistoricalAttributionStatefulInput(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier resolved through stateful integrations.",
        json_schema_extra={"example": "DEMO_DPM_EUR_001"},
    )
    as_of_date: dt.date = Field(
        description="Business date used for stateful sourcing.",
        json_schema_extra={"example": "2026-02-28"},
    )
    client_id: str | None = Field(
        default=None,
        description="Optional client identifier for policy-controlled upstream sourcing.",
        json_schema_extra={"example": "CLIENT_1000123"},
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Optional reporting currency override.",
        json_schema_extra={"example": "USD"},
    )
    net_or_gross: Literal["NET", "GROSS"] = Field(
        default="NET",
        description="Whether sourced returns are net or gross.",
        json_schema_extra={"example": "NET"},
    )
    periods: list[RiskRequestPeriod] = Field(
        description="List of periods to evaluate historical attribution.",
        json_schema_extra={"example": [{"type": "YTD", "name": "YTD"}]},
    )
    attribution_options: AttributionOptions = Field(
        default_factory=AttributionOptions,
        description="Historical attribution options for stateful execution.",
        json_schema_extra={
            "example": {
                "attribution_types": ["TOTAL_RISK"],
                "metrics": ["VOLATILITY"],
                "grouping_dimensions": ["SECTOR"],
            }
        },
    )

    @model_validator(mode="after")
    def validate_semantics(self) -> "HistoricalAttributionStatefulInput":
        _validate_unique_period_names(self.periods)

        grouping_dimensions = self.attribution_options.grouping_dimensions
        if "CUSTOM" in grouping_dimensions:
            raise ValueError(
                "stateful historical-attribution does not support grouping_dimension=CUSTOM"
            )

        return self


class HistoricalAttributionRequest(BaseModel):
    input_mode: AttributionInputMode = Field(
        default=AttributionInputMode.STATELESS,
        description="Execution mode for historical attribution analytics.",
        json_schema_extra={"example": "stateless"},
    )
    stateless_input: HistoricalAttributionStatelessInput | None = Field(
        default=None,
        description="Stateless payload with fully supplied returns and exposure history.",
        json_schema_extra={
            "example": {
                "scope": {"as_of_date": "2026-02-28", "net_or_gross": "NET"},
                "periods": [{"type": "YTD", "name": "YTD"}],
                "returns": [{"date": "2026-01-02", "value": 0.62}],
                "exposure_history": [
                    {
                        "date": "2026-01-02",
                        "grouping_dimension": "SECTOR",
                        "group_key": "SECTOR_TECH",
                        "weight": 0.245,
                    }
                ],
            }
        },
    )
    stateful_input: HistoricalAttributionStatefulInput | None = Field(
        default=None,
        description=(
            "Stateful payload for returns/exposure sourcing through lotus-performance and lotus-core. "
            "Stateful ACTIVE_RISK currently supports POSITION, SECTOR, ASSET_CLASS, and ISSUER; "
            "ISSUER is supported through lotus-performance benchmark exposure context issuer groups. "
            "CUSTOM grouping is not supported in stateful mode."
        ),
        json_schema_extra={
            "example": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
                "periods": [{"type": "YTD", "name": "YTD"}],
                "attribution_options": {
                    "attribution_types": ["ACTIVE_RISK"],
                    "metrics": ["TRACKING_ERROR"],
                    "grouping_dimensions": ["SECTOR"],
                    "annualization_basis": 252,
                    "covariance_method": "EMPIRICAL",
                    "min_observations_policy": "STRICT",
                },
            }
        },
    )
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": cast(Any, HISTORICAL_ATTRIBUTION_REQUEST_EXAMPLE)},
    )

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "HistoricalAttributionRequest":
        if self.input_mode == AttributionInputMode.STATELESS and self.stateless_input is None:
            raise ValueError("stateless_input is required when input_mode=stateless")
        if self.input_mode == AttributionInputMode.STATEFUL and self.stateful_input is None:
            raise ValueError("stateful_input is required when input_mode=stateful")
        return self
