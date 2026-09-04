from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.contracts.attribution_inputs import (
    ATTRIBUTION_METRIC_UNIT_SEMANTICS,
    AttributionMetric,
    AttributionType,
    AttributionValueUnit,
    GroupingDimension,
)
from app.contracts.audit import AuditMetadataFields
from app.contracts.risk import RiskCalculationSupportability


def _default_stateful_active_risk_supported_groupings() -> list[GroupingDimension]:
    return ["POSITION", "SECTOR", "ASSET_CLASS", "ISSUER"]


def _default_stateful_active_risk_gated_groupings() -> list[GroupingDimension]:
    return []


class HistoricalAttributionMetadata(AuditMetadataFields):
    product_name: Literal["HistoricalRiskAttributionReport"] = Field(
        default="HistoricalRiskAttributionReport",
        description="Source-owned domain data product emitted by this response.",
        json_schema_extra={"example": "HistoricalRiskAttributionReport"},
    )
    product_version: Literal["v1"] = Field(
        default="v1",
        description="Source-owned domain data product version.",
        json_schema_extra={"example": "v1"},
    )
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
    metric_unit_semantics: dict[AttributionMetric, AttributionValueUnit] = Field(
        description=(
            "Unit semantics per requested attribution metric, covering total_value, "
            "reconciled_sum, residual, and marginal/component contributions: "
            "decimal_ratio values are decimal fractions of one (0.1253 means 12.53%). "
            "weight_average and percent_contribution are always decimal fractions of "
            "one by field contract. Annualization is stated separately by "
            "annualization_basis and does not change how a value is read."
        ),
        json_schema_extra={
            "example": {"VOLATILITY": "decimal_ratio", "TRACKING_ERROR": "decimal_ratio"}
        },
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
    benchmark_context: dict[str, object] = Field(
        default_factory=dict,
        description="Source-owned benchmark context summary for domain-data-product trust metadata.",
        json_schema_extra={
            "example": {
                "requested": True,
                "source_service": "lotus-performance",
                "reason": "APPLIED",
            }
        },
    )

    @model_validator(mode="after")
    def validate_unit_semantics_cover_requested_metrics(self) -> HistoricalAttributionMetadata:
        # The field's promise is per REQUESTED metric, exactly: a subset would
        # leave a requested metric's values unreadable downstream, and a
        # superset would state units for values this response does not carry.
        stated = set(self.metric_unit_semantics)
        requested = set(self.requested_metrics)
        if stated != requested:
            raise ValueError(
                "metric_unit_semantics must state exactly the requested metrics; "
                f"missing={sorted(requested - stated)}, surplus={sorted(stated - requested)}"
            )
        # The unit for each metric is a source-owned FACT, not a per-response
        # choice: a mock stating VOLATILITY as unitless would make a downstream
        # formatter read 0.1253 at face value instead of as 12.53%.
        contradictions = {
            metric: unit
            for metric, unit in self.metric_unit_semantics.items()
            if unit != ATTRIBUTION_METRIC_UNIT_SEMANTICS[metric]
        }
        if contradictions:
            raise ValueError(
                "metric_unit_semantics contradicts the canonical source-owned units: "
                + ", ".join(
                    f"{metric}={unit} (canonical {ATTRIBUTION_METRIC_UNIT_SEMANTICS[metric]})"
                    for metric, unit in sorted(contradictions.items())
                )
            )
        return self

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


__all__ = ["HistoricalAttributionMetadata"]
