from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


def _default_source_services() -> list[str]:
    return ["lotus-risk"]


class AuditMetadataFields(BaseModel):
    lineage_version: Literal["risk_audit_lineage.v1"] = Field(
        default="risk_audit_lineage.v1",
        description="Audit lineage metadata schema version.",
        json_schema_extra={"example": "risk_audit_lineage.v1"},
    )
    request_fingerprint: str | None = Field(
        default=None,
        description=(
            "Deterministic SHA-256 fingerprint of the normalized calculation request used by "
            "lotus-risk. Stateful flows fingerprint the calculation input after upstream sourcing."
        ),
        json_schema_extra={
            "example": "sha256:6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c"
        },
    )
    source_services: list[str] = Field(
        default_factory=_default_source_services,
        description="Services whose data or calculations contributed to this response.",
        json_schema_extra={"example": ["lotus-risk", "lotus-performance"]},
    )
    upstream_request_fingerprints: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Deterministic request fingerprints for upstream calls directly orchestrated by "
            "lotus-risk, keyed by service and operation."
        ),
        json_schema_extra={
            "example": {
                "lotus-performance:/integration/returns/series": (
                    "sha256:8d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a1"
                )
            }
        },
    )
