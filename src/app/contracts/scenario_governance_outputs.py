from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.contracts.scenario_common_outputs import (
    ScenarioPackApplicabilityStatus,
    ScenarioPackApprovalStatus,
    ScenarioPackEffectivePeriodStatus,
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


__all__ = ["ScenarioPackGovernanceEvidence"]
