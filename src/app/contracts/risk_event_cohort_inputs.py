from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator

RISK_EVENT_ALLOCATION_TOLERANCE = 0.000001
RISK_EVENT_MAX_CANDIDATE_PORTFOLIOS = 250
RISK_EVENT_MAX_EXPOSURE_BUCKETS_PER_PORTFOLIO = 16
RISK_EVENT_MAX_RETURNED_PORTFOLIO_ROWS = RISK_EVENT_MAX_CANDIDATE_PORTFOLIOS


class RiskEventPortfolioExposure(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier to evaluate for risk-event impact.",
        json_schema_extra={"example": "PB_SG_GLOBAL_BAL_001"},
    )
    exposure_weights: dict[str, float] = Field(
        max_length=RISK_EVENT_MAX_EXPOSURE_BUCKETS_PER_PORTFOLIO,
        description=(
            "Portfolio exposure weights by risk-event exposure bucket. Weights must form a full "
            "allocation that sums to 1.0 within the governed tolerance."
        ),
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
        if any(weight > 1.0 for weight in self.exposure_weights.values()):
            raise ValueError("exposure_weights must be less than or equal to 1.0 per bucket")
        total = sum(self.exposure_weights.values())
        if abs(total - 1.0) > RISK_EVENT_ALLOCATION_TOLERANCE:
            raise ValueError(
                "exposure_weights must sum to 1.0 within "
                f"{RISK_EVENT_ALLOCATION_TOLERANCE}; received {total:.6f}"
            )
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
        max_length=RISK_EVENT_MAX_CANDIDATE_PORTFOLIOS,
        description=(
            "Candidate portfolios with source-supplied exposure weights. Returned affected and "
            f"excluded portfolio rows are bounded by {RISK_EVENT_MAX_RETURNED_PORTFOLIO_ROWS} "
            "candidate rows."
        ),
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


__all__ = [
    "RISK_EVENT_ALLOCATION_TOLERANCE",
    "RISK_EVENT_MAX_CANDIDATE_PORTFOLIOS",
    "RISK_EVENT_MAX_EXPOSURE_BUCKETS_PER_PORTFOLIO",
    "RISK_EVENT_MAX_RETURNED_PORTFOLIO_ROWS",
    "RiskEventAffectedCohortRequest",
    "RiskEventPortfolioExposure",
]
