from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.scenario_common_outputs import ScenarioSupportabilityState


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
    source_services: list[str] = Field(
        default_factory=lambda: ["lotus-risk"],
        description="Services whose data or calculations contributed to this response.",
        json_schema_extra={"example": ["lotus-risk"]},
    )
    correlation_id: str | None = Field(
        default=None,
        description="Request correlation identifier when available from the request context.",
        json_schema_extra={"example": "corr-123"},
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


__all__ = ["ScenarioEvaluationMetadata"]
