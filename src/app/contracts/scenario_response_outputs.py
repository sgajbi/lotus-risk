from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.contracts.scenario_governance_outputs import ScenarioPackGovernanceEvidence
from app.contracts.scenario_metadata_outputs import ScenarioEvaluationMetadata
from app.contracts.scenario_response_field_examples import (
    SCENARIO_GOVERNANCE_EVIDENCE_EXAMPLE,
    SCENARIO_METADATA_EXAMPLE,
    SCENARIO_REASON_CODES_EXAMPLE,
    SCENARIO_RESULTS_EXAMPLE,
)
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
        json_schema_extra={"example": SCENARIO_RESULTS_EXAMPLE},
    )
    governance_evidence: ScenarioPackGovernanceEvidence = Field(
        description=(
            "Source-owned CIO approval, effective-period, and portfolio-applicability evidence "
            "for the governed scenario pack."
        ),
        json_schema_extra={"example": SCENARIO_GOVERNANCE_EVIDENCE_EXAMPLE},
    )
    reason_codes: list[str] = Field(
        description="Bounded reason codes explaining scenario evaluation posture.",
        json_schema_extra={"example": SCENARIO_REASON_CODES_EXAMPLE},
    )
    metadata: ScenarioEvaluationMetadata = Field(
        description="Source-owned product, lineage, and supportability metadata.",
        json_schema_extra={"example": SCENARIO_METADATA_EXAMPLE},
    )


__all__ = ["RegimeScenarioPackResponse"]
