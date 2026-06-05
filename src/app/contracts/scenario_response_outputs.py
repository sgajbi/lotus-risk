from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.contracts.scenario_governance_outputs import ScenarioPackGovernanceEvidence
from app.contracts.scenario_metadata_outputs import ScenarioEvaluationMetadata
from app.contracts.scenario_result_outputs import ScenarioResult


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


__all__ = ["RegimeScenarioPackResponse"]
