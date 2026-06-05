from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ConcentrationRiskProxy(BaseModel):
    hhi_current: float = Field(
        description=(
            "Current position-level Herfindahl-Hirschman Index on the conventional 0..10000 "
            "scale, computed from positive extracted current position values."
        ),
        json_schema_extra={"example": 2450.0},
    )
    hhi_proposed: float = Field(
        description=(
            "Proposed position-level Herfindahl-Hirschman Index on the conventional 0..10000 "
            "scale after projected positions are applied; falls back to current HHI when no "
            "proposed position values are available."
        ),
        json_schema_extra={"example": 2710.0},
    )
    hhi_delta: float = Field(
        description="Proposed-minus-current position-level HHI change on the 0..10000 scale.",
        json_schema_extra={"example": 260.0},
    )


class TopPositionDriver(BaseModel):
    security_id: str | None = Field(
        default=None,
        description="Security identifier of the top concentration-driving position.",
        json_schema_extra={"example": "FO_FUND_PIMCO_INC"},
    )
    security_name: str | None = Field(
        default=None,
        description="Display name of the top concentration-driving position when available.",
        json_schema_extra={"example": "PIMCO GIS Income Fund"},
    )
    weight: float = Field(
        description="Portfolio weight of the top concentration-driving position.",
        json_schema_extra={"example": 0.23014},
    )


class SinglePositionConcentration(BaseModel):
    top_position_weight_current: float = Field(
        description=(
            "Highest single-position weight in the baseline state, computed from positive "
            "extracted position values as a decimal ratio in the 0..1 range."
        ),
        json_schema_extra={"example": 0.1245},
    )
    top_position_weight_proposed: float = Field(
        description=(
            "Highest single-position weight in the proposed state as a decimal ratio in the 0..1 "
            "range; falls back to the baseline top-position weight when no proposed position "
            "values are available."
        ),
        json_schema_extra={"example": 0.142},
    )
    top_position_weight_delta: float = Field(
        description="Proposed-minus-baseline top-position weight change as a decimal ratio.",
        json_schema_extra={"example": 0.0175},
    )
    top_n_cumulative_weight_current: float = Field(
        description=(
            "Cumulative baseline weight of the largest N positive extracted position values as "
            "a decimal ratio in the 0..1 range."
        ),
        json_schema_extra={"example": 0.4123},
    )
    top_n_cumulative_weight_proposed: float = Field(
        description=(
            "Cumulative proposed weight of the largest N positive extracted position values as "
            "a decimal ratio in the 0..1 range; falls back to the baseline top-N cumulative "
            "weight when no proposed position values are available."
        ),
        json_schema_extra={"example": 0.4551},
    )
    top_n_cumulative_weight_delta: float = Field(
        description="Proposed-minus-baseline top-N cumulative weight change as a decimal ratio.",
        json_schema_extra={"example": 0.0428},
    )
    top_n: int = Field(
        description="Top-N parameter used for cumulative single-position concentration calculations.",
        json_schema_extra={"example": 10},
    )
    top_position_current: TopPositionDriver = Field(
        description="Top baseline position driver with identifier and display metadata.",
        json_schema_extra={
            "example": {
                "security_id": "FO_FUND_PIMCO_INC",
                "security_name": "PIMCO GIS Income Fund",
                "weight": 0.23014,
            }
        },
    )
    top_position_proposed: TopPositionDriver = Field(
        description="Top proposed position driver with identifier and display metadata.",
        json_schema_extra={
            "example": {
                "security_id": "FO_FUND_PIMCO_INC",
                "security_name": "PIMCO GIS Income Fund",
                "weight": 0.22968,
            }
        },
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
        json_schema_extra={
            "example": {
                "issuer_id": "ULTIMATE_PIMCO",
                "issuer_name": "Pacific Investment Management Company LLC",
                "weight": 0.245075,
            }
        },
    )
    top_issuer_proposed: TopIssuerDriver = Field(
        description="Top proposed issuer concentration driver with identifier and display metadata.",
        json_schema_extra={
            "example": {
                "issuer_id": "ULTIMATE_PIMCO",
                "issuer_name": "Pacific Investment Management Company LLC",
                "weight": 0.244585,
            }
        },
    )
