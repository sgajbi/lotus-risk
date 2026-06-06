from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.concentration_metric_field_examples import (
    TOP_ISSUER_CURRENT_EXAMPLE,
    TOP_ISSUER_PROPOSED_EXAMPLE,
)


class TopIssuerDriver(BaseModel):
    issuer_id: str | None = Field(
        default=None,
        description="Issuer identifier of the top concentration-driving issuer bucket.",
        json_schema_extra={"example": "ULTIMATE_PIMCO"},
    )
    issuer_name: str | None = Field(
        default=None,
        description="Display name of the top concentration-driving issuer bucket when available.",
        json_schema_extra={"example": "Pacific Investment Management Company LLC"},
    )
    weight: float = Field(
        description="Portfolio weight of the top concentration-driving issuer bucket.",
        json_schema_extra={"example": 0.245075},
    )


class IssuerCoverageStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class IssuerConcentration(BaseModel):
    hhi_current: float = Field(
        description=(
            "Issuer-level baseline HHI concentration on the conventional 0 to 10000 scale, "
            "computed from covered mapped issuer buckets."
        ),
        json_schema_extra={"example": 3200.0},
    )
    hhi_proposed: float = Field(
        description=(
            "Issuer-level proposed HHI concentration on the conventional 0 to 10000 scale, "
            "falling back to baseline issuer HHI when proposed issuer buckets are unavailable."
        ),
        json_schema_extra={"example": 3475.0},
    )
    hhi_delta: float = Field(
        description="Difference between proposed and baseline issuer-level HHI concentration.",
        json_schema_extra={"example": 275.0},
    )
    top_issuer_weight_current: float = Field(
        description=(
            "Highest issuer-level baseline concentration weight from covered mapped issuer buckets."
        ),
        json_schema_extra={"example": 0.18},
    )
    top_issuer_weight_proposed: float = Field(
        description=(
            "Highest issuer-level proposed concentration weight from covered mapped issuer buckets, "
            "falling back to baseline top issuer weight when proposed issuer buckets are unavailable."
        ),
        json_schema_extra={"example": 0.21},
    )
    top_issuer_weight_delta: float = Field(
        description="Difference between proposed and baseline top issuer weights.",
        json_schema_extra={"example": 0.03},
    )
    coverage_status: IssuerCoverageStatus = Field(
        description="Coverage quality for issuer mapping used in issuer concentration calculations.",
        json_schema_extra={"example": "partial"},
    )
    covered_position_count_current: int = Field(
        description="Count of baseline positions included in issuer grouping.",
        json_schema_extra={"example": 25},
    )
    covered_position_count_proposed: int = Field(
        description="Count of proposed positions included in issuer grouping.",
        json_schema_extra={"example": 27},
    )
    total_position_count_current: int = Field(
        description="Total baseline positions evaluated for issuer coverage.",
        json_schema_extra={"example": 30},
    )
    total_position_count_proposed: int = Field(
        description="Total proposed positions evaluated for issuer coverage.",
        json_schema_extra={"example": 31},
    )
    uncovered_position_count_current: int = Field(
        description="Baseline positions without issuer coverage after enrichment resolution.",
        json_schema_extra={"example": 5},
    )
    uncovered_position_count_proposed: int = Field(
        description="Proposed positions without issuer coverage after enrichment resolution.",
        json_schema_extra={"example": 4},
    )
    coverage_ratio_current: float = Field(
        description="Covered baseline positions divided by total baseline positions.",
        json_schema_extra={"example": 0.833333},
    )
    coverage_ratio_proposed: float = Field(
        description="Covered proposed positions divided by total proposed positions.",
        json_schema_extra={"example": 0.870968},
    )
    note: str | None = Field(
        default=None,
        description="Optional diagnostics note when issuer coverage is partial or unavailable.",
        json_schema_extra={"example": "issuer_id missing in lotus-core instrument_enrichment"},
    )
    top_issuer_current: TopIssuerDriver = Field(
        description="Top baseline issuer concentration driver with identifier and display metadata.",
        json_schema_extra={"example": TOP_ISSUER_CURRENT_EXAMPLE},
    )
    top_issuer_proposed: TopIssuerDriver = Field(
        description="Top proposed issuer concentration driver with identifier and display metadata.",
        json_schema_extra={"example": TOP_ISSUER_PROPOSED_EXAMPLE},
    )


__all__ = [
    "IssuerConcentration",
    "IssuerCoverageStatus",
    "TopIssuerDriver",
]
