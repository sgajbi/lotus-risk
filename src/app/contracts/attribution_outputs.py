from __future__ import annotations

import datetime as dt
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.audit import AuditMetadataFields
from app.contracts.attribution_examples import HISTORICAL_ATTRIBUTION_RESPONSE_EXAMPLE
from app.contracts.attribution_inputs import (
    AttributionInputMode,
    AttributionMetric,
    AttributionType,
    GroupingDimension,
)
from app.contracts.risk import RiskCalculationSupportability, RiskRequestScope


def _default_stateful_active_risk_supported_groupings() -> list[GroupingDimension]:
    return ["POSITION", "SECTOR", "ASSET_CLASS", "ISSUER"]


def _default_stateful_active_risk_gated_groupings() -> list[GroupingDimension]:
    return []


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
