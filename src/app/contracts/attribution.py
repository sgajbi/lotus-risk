from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.audit import AuditMetadataFields
from app.contracts.attribution_examples import (
    HISTORICAL_ATTRIBUTION_REQUEST_EXAMPLE,
    HISTORICAL_ATTRIBUTION_RESPONSE_EXAMPLE,
)
from app.contracts.risk import (
    ReturnPoint,
    RiskCalculationSupportability,
    RiskRequestPeriod,
    RiskRequestScope,
)


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


def _default_stateful_active_risk_supported_groupings() -> list[GroupingDimension]:
    return ["POSITION", "SECTOR", "ASSET_CLASS", "ISSUER"]


def _default_stateful_active_risk_gated_groupings() -> list[GroupingDimension]:
    return []


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
        resolved_names = [period.name or period.type for period in self.periods]
        duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
        if duplicates:
            raise ValueError(
                "Duplicate period names resolved in request: "
                + ", ".join(duplicates)
                + ". Each period name (or type fallback) must be unique."
            )

        requires_active = (
            "ACTIVE_RISK" in self.attribution_options.attribution_types
            or "TRACKING_ERROR" in self.attribution_options.metrics
        )
        if requires_active:
            if not self.benchmark_returns:
                raise ValueError(
                    "benchmark_returns are required when requesting ACTIVE_RISK or TRACKING_ERROR attribution"
                )
            if not self.benchmark_exposure_history:
                raise ValueError(
                    "benchmark_exposure_history are required when requesting ACTIVE_RISK or TRACKING_ERROR attribution"
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
        resolved_names = [period.name or period.type for period in self.periods]
        duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
        if duplicates:
            raise ValueError(
                "Duplicate period names resolved in request: "
                + ", ".join(duplicates)
                + ". Each period name (or type fallback) must be unique."
            )

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
    total_value: float | None = Field(
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


class HistoricalAttributionMetadata(AuditMetadataFields):
    contract_version: str = Field(
        default="v1",
        description="Historical attribution contract version.",
        json_schema_extra={"example": "v1"},
    )
    methodology_version: str = Field(
        default="historical_attribution.v1",
        description="Methodology version used for historical attribution formulas.",
        json_schema_extra={"example": "historical_attribution.v1"},
    )
    covariance_method: Literal["EMPIRICAL"] = Field(
        description="Covariance estimator used for attribution decomposition.",
        json_schema_extra={"example": "EMPIRICAL"},
    )
    annualization_basis: int = Field(
        description="Annualization basis used for annualized metrics.",
        json_schema_extra={"example": 252},
    )
    requested_attribution_types: list[AttributionType] = Field(
        default_factory=list,
        description="Requested attribution decomposition types in canonical execution order.",
        json_schema_extra={"example": ["TOTAL_RISK", "ACTIVE_RISK"]},
    )
    requested_metrics: list[AttributionMetric] = Field(
        default_factory=list,
        description="Requested attribution metrics in canonical execution order.",
        json_schema_extra={"example": ["VOLATILITY", "TRACKING_ERROR"]},
    )
    requested_grouping_dimensions: list[GroupingDimension] = Field(
        default_factory=list,
        description="Requested grouping dimensions in canonical execution order.",
        json_schema_extra={"example": ["POSITION", "SECTOR"]},
    )
    min_observations_policy: Literal["STRICT", "ALLOW_PARTIAL"] = Field(
        description="Minimum observation policy used for attribution decomposition.",
        json_schema_extra={"example": "STRICT"},
    )
    stateful_active_risk_supported_grouping_dimensions: list[GroupingDimension] = Field(
        default_factory=_default_stateful_active_risk_supported_groupings,
        description="Grouping dimensions currently supported for stateful ACTIVE_RISK attribution.",
        json_schema_extra={"example": ["POSITION", "SECTOR", "ASSET_CLASS", "ISSUER"]},
    )
    stateful_active_risk_gated_grouping_dimensions: list[GroupingDimension] = Field(
        default_factory=_default_stateful_active_risk_gated_groupings,
        description="Grouping dimensions intentionally gated for stateful ACTIVE_RISK attribution.",
        json_schema_extra={"example": []},
    )
    stateful_active_risk_gate_reason: str = Field(
        default="none",
        description="Deterministic reason for any gated stateful ACTIVE_RISK grouping dimensions.",
        json_schema_extra={"example": "none"},
    )
    calculation_supportability: RiskCalculationSupportability = Field(
        default_factory=lambda: RiskCalculationSupportability(
            state="ready",
            reason="calculation_complete",
            freshness_bucket="unknown",
        ),
        description="Source-backed supportability posture for UI and operator consumption.",
        json_schema_extra={
            "example": {
                "state": "ready",
                "reason": "calculation_complete",
                "freshness_bucket": "current",
                "degraded_metric_count": 0,
                "empty_period_count": 0,
                "evaluated_period_count": 1,
            }
        },
    )


class HistoricalAttributionResponse(BaseModel):
    source_service: Literal["lotus-risk"] = Field(
        default="lotus-risk",
        description="Service identifier producing this attribution response.",
        json_schema_extra={"example": "lotus-risk"},
    )
    input_mode: AttributionInputMode = Field(
        description="Execution mode used to produce this response.",
        json_schema_extra={"example": "stateless"},
    )
    scope: RiskRequestScope = Field(
        description="Normalized scope context used for attribution calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    results: dict[str, HistoricalAttributionPeriodResult] = Field(
        description="Period-level attribution results keyed by period name.",
        json_schema_extra={
            "example": {
                "YTD": {
                    "start_date": "2026-01-01",
                    "end_date": "2026-02-28",
                    "attribution_sets": [],
                    "error": None,
                }
            }
        },
    )
    metadata: HistoricalAttributionMetadata = Field(
        description="Historical attribution contract and methodology metadata.",
        json_schema_extra={
            "example": {
                "contract_version": "v1",
                "methodology_version": "historical_attribution.v1",
                "covariance_method": "EMPIRICAL",
                "annualization_basis": 252,
                "requested_attribution_types": ["TOTAL_RISK", "ACTIVE_RISK"],
                "requested_metrics": ["VOLATILITY", "TRACKING_ERROR"],
                "requested_grouping_dimensions": ["SECTOR"],
                "min_observations_policy": "STRICT",
                "stateful_active_risk_supported_grouping_dimensions": [
                    "POSITION",
                    "SECTOR",
                    "ASSET_CLASS",
                    "ISSUER",
                ],
                "stateful_active_risk_gated_grouping_dimensions": [],
                "stateful_active_risk_gate_reason": "none",
            }
        },
    )
    model_config = ConfigDict(
        json_schema_extra={"example": cast(Any, HISTORICAL_ATTRIBUTION_RESPONSE_EXAMPLE)}
    )
