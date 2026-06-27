from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from app.contracts.audit import AuditMetadataFields
from app.contracts.concentration_inputs import EnrichmentPolicy, IssuerGroupingLevel
from app.contracts.risk import RiskCalculationSupportability


class ConcentrationMetadata(AuditMetadataFields):
    as_of_date: date | None = Field(
        default=None,
        description="Business date used for baseline/proposed concentration inputs.",
        json_schema_extra={"example": "2026-02-27"},
    )
    portfolio_id: str | None = Field(
        default=None,
        description="Portfolio identifier when stateful or simulation mode is used.",
        json_schema_extra={"example": "DEMO_DPM_EUR_001"},
    )
    correlation_id: str | None = Field(
        default=None,
        description="Request correlation identifier carried through source calls and response metadata.",
        json_schema_extra={"example": "corr-123"},
    )
    simulation_session_id: str | None = Field(
        default=None,
        description="Simulation session identifier for simulation mode responses.",
        json_schema_extra={"example": "SIM_0001"},
    )
    simulation_session_version: int | None = Field(
        default=None,
        description="Simulation session version resolved by lotus-core.",
        json_schema_extra={"example": 3},
    )
    session_expires_at: datetime | None = Field(
        default=None,
        description="Session expiration timestamp returned by lotus-core when session lifecycle is created.",
        json_schema_extra={"example": "2026-02-28T10:30:00Z"},
    )
    issuer_grouping_level: IssuerGroupingLevel = Field(
        description="Issuer grouping level applied to issuer concentration calculations.",
        json_schema_extra={"example": "ultimate_parent"},
    )
    enrichment_policy: EnrichmentPolicy = Field(
        description="Issuer enrichment policy applied for issuer concentration calculations.",
        json_schema_extra={"example": "merge_caller_then_core"},
    )
    include_cash_positions: bool | None = Field(
        default=None,
        description="Whether cash positions were included in the evaluated concentration universe.",
        json_schema_extra={"example": True},
    )
    include_zero_quantity_positions: bool | None = Field(
        default=None,
        description="Whether zero-quantity positions were included in the evaluated concentration universe.",
        json_schema_extra={"example": False},
    )
    calculation_supportability: RiskCalculationSupportability = Field(
        default_factory=lambda: RiskCalculationSupportability(
            state="ready",
            reason="calculation_complete",
            freshness_bucket="unknown",
        ),
        description="Source-backed supportability posture for UI and operator consumption.",
        json_schema_extra={
            "example": {
                "state": "ready",
                "reason": "calculation_complete",
                "freshness_bucket": "unknown",
                "degraded_metric_count": 0,
                "empty_period_count": 0,
                "evaluated_period_count": 1,
            }
        },
    )


__all__ = ["ConcentrationMetadata"]
