from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.contracts.risk_event_cohort_metadata import RiskEventCohortMetadata
from app.contracts.risk_event_cohort_portfolio_outputs import (
    RiskEventAffectedPortfolio,
    RiskEventExcludedPortfolio,
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
                    "mandate_id": "MANDATE-PB-SG-LOW-RISK-002",
                    "portfolio_manager_id": "pm-singapore-01",
                    "impact_score": 0.015,
                    "dominant_bucket": "FIXED_INCOME",
                    "bucket_impacts": {"FIXED_INCOME": -0.015, "CASH": 0.0},
                    "source_ref": (
                        "risk-event-cohort:RISK_EVENT_2026_Q2_RATES_UP:"
                        "2026-05-10:PB_SG_LOW_RISK_002"
                    ),
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


__all__ = ["RiskEventAffectedCohortResponse"]
