from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ScenarioSupportabilityState(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    PENDING_REVIEW = "pending_review"
    BLOCKED = "blocked"


class ScenarioPackApprovalStatus(StrEnum):
    APPROVED = "approved"
    NOT_APPROVED = "not_approved"


class ScenarioPackEffectivePeriodStatus(StrEnum):
    ACTIVE = "active"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    EXPIRED = "expired"


class ScenarioPackApplicabilityStatus(StrEnum):
    APPLICABLE = "applicable"
    PENDING_REVIEW = "pending_review"
    NOT_APPLICABLE = "not_applicable"


class ScenarioExposure(BaseModel):
    bucket: str = Field(
        description="Risk scenario exposure bucket.",
        json_schema_extra={"example": "EQUITY"},
    )
    weight: float = Field(
        ge=0.0,
        description="Portfolio weight for this exposure bucket.",
        json_schema_extra={"example": 0.55},
    )


class ScenarioExposureComponent(BaseModel):
    security_id: str = Field(
        description="Security or instrument identifier contributing to the scenario bucket.",
        json_schema_extra={"example": "FO_EQ_AAPL_US"},
    )
    display_name: str | None = Field(
        default=None,
        description="Optional display name for the contributing security or instrument.",
        json_schema_extra={"example": "Apple Inc."},
    )
    bucket: str = Field(
        description="Scenario bucket used for the security contribution.",
        json_schema_extra={"example": "EQUITY"},
    )
    weight: float = Field(
        ge=0.0,
        description="Portfolio weight represented by this security contribution.",
        json_schema_extra={"example": 0.18},
    )


class RegimeScenarioPackRequest(BaseModel):
    scenario_pack_id: str = Field(
        description="Governed scenario pack identifier.",
        json_schema_extra={"example": "CIO_REGIME_2026_Q2"},
    )
    portfolio_id: str | None = Field(
        default=None,
        description="Optional portfolio identifier used for lineage and diagnostics.",
        json_schema_extra={"example": "PB_SG_GLOBAL_BAL_001"},
    )
    as_of_date: dt.date = Field(
        description="Business date for the scenario-pack evaluation.",
        json_schema_extra={"example": "2026-05-03"},
    )
    exposures: list[ScenarioExposure] = Field(
        description="Caller-supplied portfolio exposure weights by scenario bucket.",
        json_schema_extra={
            "example": [
                {"bucket": "EQUITY", "weight": 0.55},
                {"bucket": "FIXED_INCOME", "weight": 0.35},
                {"bucket": "CASH", "weight": 0.10},
            ]
        },
    )
    exposure_components: list[ScenarioExposureComponent] = Field(
        default_factory=list,
        description=(
            "Optional position-level exposure components used to emit per-security scenario "
            "contribution rows. When supplied, component weights must reconcile to the bucket "
            "weights in exposures."
        ),
        json_schema_extra={
            "example": [
                {
                    "security_id": "FO_EQ_AAPL_US",
                    "display_name": "Apple Inc.",
                    "bucket": "EQUITY",
                    "weight": 0.18,
                },
                {
                    "security_id": "FO_BOND_UST_2030",
                    "display_name": "United States Treasury 3.875% 2030",
                    "bucket": "FIXED_INCOME",
                    "weight": 0.35,
                },
            ]
        },
    )
    maximum_allowed_loss_pct: float = Field(
        ge=0.0,
        le=1.0,
        description="Maximum permitted scenario loss ratio for the consumer policy.",
        json_schema_extra={"example": 0.12},
    )

    @model_validator(mode="after")
    def validate_exposures(self) -> "RegimeScenarioPackRequest":
        if not self.exposures:
            raise ValueError("exposures must contain at least one scenario exposure bucket")
        if self.exposure_components:
            exposure_by_bucket = {
                exposure.bucket.upper(): exposure.weight for exposure in self.exposures
            }
            component_totals: dict[str, float] = {}
            for component in self.exposure_components:
                bucket = component.bucket.upper()
                component_totals[bucket] = component_totals.get(bucket, 0.0) + component.weight
            unknown_component_buckets = sorted(set(component_totals) - set(exposure_by_bucket))
            if unknown_component_buckets:
                raise ValueError(
                    "exposure_components contain buckets absent from exposures: "
                    + ", ".join(unknown_component_buckets)
                )
            mismatched_buckets = [
                bucket
                for bucket, component_weight in sorted(component_totals.items())
                if abs(component_weight - exposure_by_bucket[bucket]) > 0.000001
            ]
            if mismatched_buckets:
                raise ValueError(
                    "exposure_components must reconcile to exposures for buckets: "
                    + ", ".join(mismatched_buckets)
                )
        return self


class ScenarioPositionContribution(BaseModel):
    security_id: str = Field(
        description="Security or instrument identifier for the scenario contribution row.",
        json_schema_extra={"example": "FO_EQ_AAPL_US"},
    )
    display_name: str | None = Field(
        default=None,
        description="Optional display name for the contributing security or instrument.",
        json_schema_extra={"example": "Apple Inc."},
    )
    bucket: str = Field(
        description="Scenario bucket used to assign the risk shock.",
        json_schema_extra={"example": "EQUITY"},
    )
    weight: float = Field(
        ge=0.0,
        description="Portfolio weight used for this security contribution.",
        json_schema_extra={"example": 0.18},
    )
    shock_pct: float = Field(
        description="Scenario shock ratio applied to the security contribution bucket.",
        json_schema_extra={"example": -0.12},
    )
    contribution_loss_pct: float = Field(
        ge=0.0,
        description="Non-negative contribution to expected portfolio loss under the scenario.",
        json_schema_extra={"example": 0.0216},
    )


class ScenarioPackGovernanceEvidence(BaseModel):
    cio_approval_status: ScenarioPackApprovalStatus = Field(
        description="Source-owned CIO approval status for the governed scenario pack.",
        json_schema_extra={"example": "approved"},
    )
    cio_approval_ref: str = Field(
        description="Source-owned approval reference for the governed scenario pack.",
        json_schema_extra={"example": "CIO-REGIME-2026-Q2-APPROVAL"},
    )
    approved_by: str = Field(
        description="Approving CIO or risk-governance body.",
        json_schema_extra={"example": "CIO Risk Committee"},
    )
    approved_at: dt.datetime = Field(
        description="Timestamp when the scenario pack was approved.",
        json_schema_extra={"example": "2026-04-15T09:00:00Z"},
    )
    effective_from: dt.date = Field(
        description="First as-of date for which the scenario pack is effective.",
        json_schema_extra={"example": "2026-04-01"},
    )
    effective_to: dt.date = Field(
        description="Last as-of date for which the scenario pack is effective.",
        json_schema_extra={"example": "2026-06-30"},
    )
    effective_period_status: ScenarioPackEffectivePeriodStatus = Field(
        description="Source-owned effective-period posture for the requested as-of date.",
        json_schema_extra={"example": "active"},
    )
    applicability_status: ScenarioPackApplicabilityStatus = Field(
        description="Source-owned portfolio applicability posture for this scenario-pack request.",
        json_schema_extra={"example": "applicable"},
    )
    applicability_scope: list[str] = Field(
        description="Governed portfolio or mandate scope labels for which this pack is approved.",
        json_schema_extra={"example": ["DISCRETIONARY_PRIVATE_BANKING_BALANCED"]},
    )
    portfolio_applicability_ref: str | None = Field(
        default=None,
        description="Source-owned reference proving the requested portfolio is in scope when known.",
        json_schema_extra={"example": "CIO-REGIME-2026-Q2-APP-PB_SG_GLOBAL_BAL_001"},
    )
    methodology_ref: str = Field(
        description="Methodology document or lineage reference for scenario and governance posture.",
        json_schema_extra={
            "example": "docs/methodologies/metrics/regime-scenario-pack-evaluation.md"
        },
    )


class ScenarioResult(BaseModel):
    scenario_id: str = Field(
        description="Scenario identifier within the governed pack.",
        json_schema_extra={"example": "growth_slowdown"},
    )
    display_name: str = Field(
        description="Scenario display name.",
        json_schema_extra={"example": "Growth slowdown"},
    )
    expected_loss_pct: float = Field(
        description="Expected portfolio loss ratio under this scenario.",
        json_schema_extra={"example": 0.0845},
    )
    shock_by_bucket: dict[str, float] = Field(
        description="Scenario shock ratios by exposure bucket.",
        json_schema_extra={"example": {"EQUITY": -0.12, "FIXED_INCOME": -0.03}},
    )
    position_contributions: list[ScenarioPositionContribution] = Field(
        default_factory=list,
        description=(
            "Optional per-security contribution rows when exposure_components were supplied. "
            "Rows are source-owned scenario contribution evidence, not a full repricing model."
        ),
        json_schema_extra={
            "example": [
                {
                    "security_id": "FO_EQ_AAPL_US",
                    "display_name": "Apple Inc.",
                    "bucket": "EQUITY",
                    "weight": 0.18,
                    "shock_pct": -0.12,
                    "contribution_loss_pct": 0.0216,
                }
            ]
        },
    )


class ScenarioEvaluationMetadata(BaseModel):
    product_name: str = Field(
        default="RegimeScenarioPackEvaluation",
        description="Source-owned product name.",
        json_schema_extra={"example": "RegimeScenarioPackEvaluation"},
    )
    product_version: str = Field(
        default="v1",
        description="Source-owned product version.",
        json_schema_extra={"example": "v1"},
    )
    source_service: str = Field(
        default="lotus-risk",
        description="Authoritative source service.",
        json_schema_extra={"example": "lotus-risk"},
    )
    lineage_version: str = Field(
        default="risk-regime-scenario-pack-evaluation.v1",
        description="Lineage policy version used for this evaluation.",
        json_schema_extra={"example": "risk-regime-scenario-pack-evaluation.v1"},
    )
    request_fingerprint: str = Field(
        description="Deterministic request fingerprint for replay and audit.",
        json_schema_extra={"example": "sha256:abc123"},
    )
    calculation_supportability: ScenarioSupportabilityState = Field(
        description="Source-owned supportability posture.",
        json_schema_extra={"example": "ready"},
    )


class RegimeScenarioPackResponse(BaseModel):
    scenario_pack_id: str = Field(
        description="Governed scenario pack identifier.",
        json_schema_extra={"example": "CIO_REGIME_2026_Q2"},
    )
    portfolio_id: str | None = Field(
        default=None,
        description="Portfolio identifier when supplied by the caller.",
        json_schema_extra={"example": "PB_SG_GLOBAL_BAL_001"},
    )
    as_of_date: dt.date = Field(
        description="Business date for the evaluation.",
        json_schema_extra={"example": "2026-05-03"},
    )
    worst_case_loss_pct: float = Field(
        description="Largest expected portfolio loss ratio across scenarios.",
        json_schema_extra={"example": 0.0845},
    )
    maximum_allowed_loss_pct: float = Field(
        description="Consumer-supplied maximum permitted scenario loss ratio.",
        json_schema_extra={"example": 0.12},
    )
    breach: bool = Field(
        description="Whether worst_case_loss_pct exceeds maximum_allowed_loss_pct.",
        json_schema_extra={"example": False},
    )
    scenario_results: list[ScenarioResult] = Field(
        description="Per-scenario loss results from the governed scenario pack.",
        json_schema_extra={
            "example": [
                {
                    "scenario_id": "growth_slowdown",
                    "display_name": "Growth slowdown",
                    "expected_loss_pct": 0.0765,
                    "shock_by_bucket": {"EQUITY": -0.12, "FIXED_INCOME": -0.03},
                    "position_contributions": [
                        {
                            "security_id": "FO_EQ_AAPL_US",
                            "display_name": "Apple Inc.",
                            "bucket": "EQUITY",
                            "weight": 0.18,
                            "shock_pct": -0.12,
                            "contribution_loss_pct": 0.0216,
                        }
                    ],
                }
            ]
        },
    )
    governance_evidence: ScenarioPackGovernanceEvidence = Field(
        description=(
            "Source-owned CIO approval, effective-period, and portfolio-applicability evidence "
            "for the governed scenario pack."
        ),
        json_schema_extra={
            "example": {
                "cio_approval_status": "approved",
                "cio_approval_ref": "CIO-REGIME-2026-Q2-APPROVAL",
                "approved_by": "CIO Risk Committee",
                "approved_at": "2026-04-15T09:00:00Z",
                "effective_from": "2026-04-01",
                "effective_to": "2026-06-30",
                "effective_period_status": "active",
                "applicability_status": "applicable",
                "applicability_scope": ["DISCRETIONARY_PRIVATE_BANKING_BALANCED"],
                "portfolio_applicability_ref": ("CIO-REGIME-2026-Q2-APP-PB_SG_GLOBAL_BAL_001"),
                "methodology_ref": (
                    "docs/methodologies/metrics/regime-scenario-pack-evaluation.md"
                ),
            }
        },
    )
    reason_codes: list[str] = Field(
        description="Bounded reason codes explaining scenario evaluation posture.",
        json_schema_extra={"example": ["REGIME_SCENARIO_PACK_READY"]},
    )
    metadata: ScenarioEvaluationMetadata = Field(
        description="Source-owned product, lineage, and supportability metadata.",
        json_schema_extra={
            "example": {
                "product_name": "RegimeScenarioPackEvaluation",
                "product_version": "v1",
                "source_service": "lotus-risk",
                "lineage_version": "risk-regime-scenario-pack-evaluation.v1",
                "request_fingerprint": "sha256:abc123",
                "calculation_supportability": "ready",
            }
        },
    )
