from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ScenarioSupportabilityState(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    PENDING_REVIEW = "pending_review"
    BLOCKED = "blocked"


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
        return self


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
                }
            ]
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
