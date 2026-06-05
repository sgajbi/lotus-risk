from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ConcentrationInputMode(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"
    SIMULATION = "simulation"


class IssuerGroupingLevel(str, Enum):
    LEGAL_ISSUER = "legal_issuer"
    ULTIMATE_PARENT = "ultimate_parent"


class EnrichmentPolicy(str, Enum):
    USE_CALLER_ONLY = "use_caller_only"
    MERGE_CALLER_THEN_CORE = "merge_caller_then_core"
    CORE_ONLY = "core_only"


class CurrentPosition(BaseModel):
    security_id: str = Field(
        description="Canonical security identifier in the baseline portfolio state.",
        json_schema_extra={"example": "AAPL.US"},
    )
    security_name: str | None = Field(
        default=None,
        description="Optional security display name for user-facing concentration interpretation.",
        json_schema_extra={"example": "Apple Inc."},
    )
    quantity: float | None = Field(
        default=None,
        description="Baseline quantity for the position.",
        json_schema_extra={"example": 1000.0},
    )
    market_value_base: float | None = (  # monetary-float-allow: concentration DTO.
        Field(
            default=None,
            description="Optional baseline market value in reporting currency.",
            json_schema_extra={"example": 19500.25},
        )
    )
    weight: float | None = Field(
        default=None,
        description="Optional baseline portfolio weight for this position.",
        json_schema_extra={"example": 0.1245},
    )
    issuer_id: str | None = Field(
        default=None,
        description="Optional canonical issuer identifier for issuer concentration grouping.",
        json_schema_extra={"example": "ISSUER_APPLE_INC"},
    )
    ultimate_parent_issuer_id: str | None = Field(
        default=None,
        description="Optional ultimate parent issuer identifier for parent-level issuer concentration grouping.",
        json_schema_extra={"example": "ISSUER_APPLE_HOLDING"},
    )


class ProjectedPosition(BaseModel):
    security_id: str = Field(
        description="Canonical security identifier in the projected portfolio state.",
        json_schema_extra={"example": "AAPL.US"},
    )
    security_name: str | None = Field(
        default=None,
        description="Optional projected security display name for user-facing concentration interpretation.",
        json_schema_extra={"example": "Apple Inc."},
    )
    proposed_quantity: float | None = Field(
        default=None,
        description="Projected quantity for simulation or concentration what-if analysis.",
        json_schema_extra={"example": 1200.0},
    )
    projected_market_value_base: float | None = (  # monetary-float-allow: concentration DTO.
        Field(
            default=None,
            description="Optional projected market value in reporting currency.",
            json_schema_extra={"example": 23400.3},
        )
    )
    projected_weight: float | None = Field(
        default=None,
        description="Optional projected portfolio weight for this position.",
        json_schema_extra={"example": 0.142},
    )
    issuer_id: str | None = Field(
        default=None,
        description="Optional canonical issuer identifier for issuer concentration grouping.",
        json_schema_extra={"example": "ISSUER_APPLE_INC"},
    )
    ultimate_parent_issuer_id: str | None = Field(
        default=None,
        description="Optional ultimate parent issuer identifier for parent-level issuer concentration grouping.",
        json_schema_extra={"example": "ISSUER_APPLE_HOLDING"},
    )


class IssuerMappingInput(BaseModel):
    security_id: str = Field(
        description="Security identifier mapped to issuer keys for concentration enrichment overrides.",
        json_schema_extra={"example": "SEC_AAPL_US"},
    )
    issuer_id: str | None = Field(
        default=None,
        description="Legal issuer identifier mapped to this security.",
        json_schema_extra={"example": "ISSUER_APPLE_INC"},
    )
    issuer_name: str | None = Field(
        default=None,
        description="Legal issuer display name mapped to this security.",
        json_schema_extra={"example": "Apple Inc."},
    )
    ultimate_parent_issuer_id: str | None = Field(
        default=None,
        description="Ultimate parent issuer identifier mapped to this security.",
        json_schema_extra={"example": "ISSUER_APPLE_HOLDING"},
    )
    ultimate_parent_issuer_name: str | None = Field(
        default=None,
        description="Ultimate parent issuer display name mapped to this security.",
        json_schema_extra={"example": "Apple Holdings PLC"},
    )


__all__ = [
    "ConcentrationInputMode",
    "CurrentPosition",
    "EnrichmentPolicy",
    "IssuerGroupingLevel",
    "IssuerMappingInput",
    "ProjectedPosition",
]
