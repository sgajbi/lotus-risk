from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.risk_event_cohort_common import RiskEventCohortSupportabilityState


class RiskEventCohortMetadata(BaseModel):
    product_name: str = Field(
        default="RiskEventAffectedCohort",
        description="Source-owned product name.",
        json_schema_extra={"example": "RiskEventAffectedCohort"},
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
    lineage_version: str = Field(
        default="risk-event-affected-cohort.v1",
        description="Lineage policy version used for this cohort evaluation.",
        json_schema_extra={"example": "risk-event-affected-cohort.v1"},
    )
    request_fingerprint: str = Field(
        description="Deterministic request fingerprint for replay and audit.",
        json_schema_extra={"example": "sha256:abc123"},
    )
    calculation_supportability: RiskEventCohortSupportabilityState = Field(
        description="Source-owned supportability posture for the cohort.",
        json_schema_extra={"example": "ready"},
    )


__all__ = ["RiskEventCohortMetadata"]
