from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class RiskEventCohortSupportabilityState(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    PENDING_REVIEW = "pending_review"
    BLOCKED = "blocked"


class RiskEventPortfolioExposure(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier to evaluate for risk-event impact.",
        json_schema_extra={"example": "PB_SG_GLOBAL_BAL_001"},
    )
    exposure_weights: dict[str, float] = Field(
        description="Portfolio exposure weights by risk-event exposure bucket.",
        json_schema_extra={"example": {"EQUITY": 0.55, "FIXED_INCOME": 0.35, "CASH": 0.10}},
    )
    mandate_id: str | None = Field(
        default=None,
        description="Optional mandate identifier preserved for downstream wave lineage.",
        json_schema_extra={"example": "MANDATE-PB-SG-GLOBAL-BAL-001"},
    )
    portfolio_manager_id: str | None = Field(
        default=None,
        description="Optional portfolio-manager identifier preserved for downstream review routing.",
        json_schema_extra={"example": "pm-singapore-01"},
    )

    @model_validator(mode="after")
    def validate_exposure_weights(self) -> "RiskEventPortfolioExposure":
        if not self.exposure_weights:
            raise ValueError("exposure_weights must contain at least one exposure bucket")
        if any(weight < 0 for weight in self.exposure_weights.values()):
            raise ValueError("exposure_weights must be non-negative")
        return self


class RiskEventAffectedCohortRequest(BaseModel):
    risk_event_id: str = Field(
        description="Governed risk-event identifier.",
        json_schema_extra={"example": "RISK_EVENT_2026_Q2_RATES_UP"},
    )
    as_of_date: dt.date = Field(
        description="Business date for the cohort evaluation.",
        json_schema_extra={"example": "2026-05-10"},
    )
    portfolios: list[RiskEventPortfolioExposure] = Field(
        description="Candidate portfolios with source-supplied exposure weights.",
        json_schema_extra={
            "example": [
                {
                    "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                    "mandate_id": "MANDATE-PB-SG-GLOBAL-BAL-001",
                    "portfolio_manager_id": "pm-singapore-01",
                    "exposure_weights": {"EQUITY": 0.55, "FIXED_INCOME": 0.35, "CASH": 0.10},
                }
            ]
        },
    )
    minimum_impact_score: float = Field(
        default=0.05,
        ge=0.0,
        description="Minimum absolute event-impact score required for cohort inclusion.",
        json_schema_extra={"example": 0.05},
    )

    @model_validator(mode="after")
    def validate_candidate_portfolios(self) -> "RiskEventAffectedCohortRequest":
        if not self.portfolios:
            raise ValueError("portfolios must contain at least one candidate portfolio")
        return self


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


class RiskEventAffectedCohortResponse(BaseModel):
    cohort_id: str = Field(
        description="Deterministic affected-cohort identifier.",
        json_schema_extra={"example": "risk_event_cohort_7f4d2a1c"},
    )
    risk_event_id: str = Field(
        description="Governed risk-event identifier.",
        json_schema_extra={"example": "RISK_EVENT_2026_Q2_RATES_UP"},
    )
    display_name: str = Field(
        description="Business display name for the governed risk event.",
        json_schema_extra={"example": "Rates-up inflation persistence"},
    )
    as_of_date: dt.date = Field(
        description="Business date for the cohort evaluation.",
        json_schema_extra={"example": "2026-05-10"},
    )
    affected_portfolios: list[RiskEventAffectedPortfolio] = Field(
        description="Portfolios whose source-owned risk-event impact meets the inclusion threshold.",
        json_schema_extra={
            "example": [
                {
                    "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                    "mandate_id": "MANDATE-PB-SG-GLOBAL-BAL-001",
                    "portfolio_manager_id": "pm-singapore-01",
                    "impact_score": 0.0745,
                    "dominant_bucket": "FIXED_INCOME",
                    "bucket_impacts": {"EQUITY": -0.022, "FIXED_INCOME": -0.0525, "CASH": 0.0},
                    "source_ref": (
                        "risk-event-cohort:RISK_EVENT_2026_Q2_RATES_UP:"
                        "2026-05-10:PB_SG_GLOBAL_BAL_001"
                    ),
                    "reason_codes": ["RISK_EVENT_THRESHOLD_BREACHED"],
                }
            ]
        },
    )
    excluded_portfolios: list[RiskEventExcludedPortfolio] = Field(
        description="Candidate portfolios excluded with explicit source-owner reason codes.",
        json_schema_extra={
            "example": [
                {
                    "portfolio_id": "PB_SG_LOW_RISK_002",
                    "impact_score": 0.015,
                    "reason_codes": ["RISK_EVENT_BELOW_THRESHOLD"],
                }
            ]
        },
    )
    reason_codes: list[str] = Field(
        description="Bounded reason codes explaining overall cohort posture.",
        json_schema_extra={"example": ["RISK_EVENT_AFFECTED_COHORT_READY"]},
    )
    metadata: RiskEventCohortMetadata = Field(
        description="Source-owned product, lineage, and supportability metadata.",
        json_schema_extra={
            "example": {
                "product_name": "RiskEventAffectedCohort",
                "product_version": "v1",
                "source_service": "lotus-risk",
                "lineage_version": "risk-event-affected-cohort.v1",
                "request_fingerprint": "sha256:abc123",
                "calculation_supportability": "ready",
            }
        },
    )
