from __future__ import annotations

from pydantic import BaseModel, Field


class RiskEventAffectedPortfolio(BaseModel):
    portfolio_id: str = Field(
        description="Affected portfolio identifier.",
        json_schema_extra={"example": "PB_SG_GLOBAL_BAL_001"},
    )
    mandate_id: str | None = Field(
        default=None,
        description="Mandate identifier when supplied by the caller.",
        json_schema_extra={"example": "MANDATE-PB-SG-GLOBAL-BAL-001"},
    )
    portfolio_manager_id: str | None = Field(
        default=None,
        description="Portfolio-manager identifier when supplied by the caller.",
        json_schema_extra={"example": "pm-singapore-01"},
    )
    impact_score: float = Field(
        description="Source-owned absolute risk-event impact score.",
        json_schema_extra={"example": 0.073},
    )
    dominant_bucket: str = Field(
        description="Exposure bucket contributing the largest absolute event impact.",
        json_schema_extra={"example": "FIXED_INCOME"},
    )
    bucket_impacts: dict[str, float] = Field(
        description="Signed event-impact contribution by exposure bucket.",
        json_schema_extra={"example": {"FIXED_INCOME": -0.0525, "EQUITY": -0.022}},
    )
    source_ref: str = Field(
        description="Stable source reference for downstream wave lineage.",
        json_schema_extra={
            "example": "risk-event-cohort:RISK_EVENT_2026_Q2_RATES_UP:PB_SG_GLOBAL_BAL_001"
        },
    )
    reason_codes: list[str] = Field(
        description="Bounded source-owner reason codes for this affected portfolio.",
        json_schema_extra={"example": ["RISK_EVENT_THRESHOLD_BREACHED"]},
    )


class RiskEventExcludedPortfolio(BaseModel):
    portfolio_id: str = Field(
        description="Candidate portfolio excluded from the affected cohort.",
        json_schema_extra={"example": "PB_SG_GLOBAL_INC_002"},
    )
    impact_score: float = Field(
        description="Source-owned absolute impact score used for exclusion.",
        json_schema_extra={"example": 0.013},
    )
    reason_codes: list[str] = Field(
        description="Bounded source-owner reason codes explaining exclusion.",
        json_schema_extra={"example": ["RISK_EVENT_BELOW_THRESHOLD"]},
    )


__all__ = [
    "RiskEventAffectedPortfolio",
    "RiskEventExcludedPortfolio",
]
