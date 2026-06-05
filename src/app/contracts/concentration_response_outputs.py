from __future__ import annotations

from datetime import date, datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.audit import AuditMetadataFields
from app.contracts.concentration_examples import CONCENTRATION_RESPONSE_EXAMPLES
from app.contracts.concentration_inputs import (
    ConcentrationInputMode,
    EnrichmentPolicy,
    IssuerGroupingLevel,
)
from app.contracts.concentration_metric_outputs import (
    ConcentrationRiskProxy,
    IssuerConcentration,
    SinglePositionConcentration,
)
from app.contracts.risk import RiskCalculationSupportability


class ConcentrationValuationContext(BaseModel):
    portfolio_currency: str | None = Field(
        default=None,
        description="Portfolio base currency provided by lotus-core valuation context.",
        json_schema_extra={"example": "EUR"},
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Reporting currency used for concentration valuation inputs.",
        json_schema_extra={"example": "USD"},
    )
    position_basis: str | None = Field(
        default=None,
        description="Position basis used by lotus-core snapshot response.",
        json_schema_extra={"example": "market_value_base"},
    )
    weight_basis: str | None = Field(
        default=None,
        description="Weight basis used by lotus-core snapshot response.",
        json_schema_extra={"example": "total_market_value_base"},
    )


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


class ConcentrationResponse(BaseModel):
    source_service: str = Field(
        description="Service identifier that produced this concentration analytics result.",
        json_schema_extra={"example": "lotus-risk"},
    )
    input_mode: ConcentrationInputMode = Field(
        description="Execution mode used for this concentration response.",
        json_schema_extra={"example": "simulation"},
    )
    risk_proxy: ConcentrationRiskProxy = Field(
        description="HHI concentration risk analytics payload.",
        json_schema_extra={
            "example": {"hhi_current": 2450.0, "hhi_proposed": 2710.0, "hhi_delta": 260.0}
        },
    )
    single_position_concentration: SinglePositionConcentration = Field(
        description="Single-position concentration analytics payload.",
        json_schema_extra={
            "example": {
                "top_position_weight_current": 0.1245,
                "top_position_weight_proposed": 0.142,
                "top_position_weight_delta": 0.0175,
                "top_n_cumulative_weight_current": 0.4123,
                "top_n_cumulative_weight_proposed": 0.4551,
                "top_n_cumulative_weight_delta": 0.0428,
                "top_n": 10,
                "top_position_current": {
                    "security_id": "FO_FUND_PIMCO_INC",
                    "security_name": "PIMCO GIS Income Fund",
                    "weight": 0.1245,
                },
                "top_position_proposed": {
                    "security_id": "FO_FUND_PIMCO_INC",
                    "security_name": "PIMCO GIS Income Fund",
                    "weight": 0.142,
                },
            }
        },
    )
    issuer_concentration: IssuerConcentration = Field(
        description="Issuer-level concentration analytics payload with coverage diagnostics.",
        json_schema_extra={
            "example": {
                "hhi_current": 3200.0,
                "hhi_proposed": 3475.0,
                "hhi_delta": 275.0,
                "top_issuer_weight_current": 0.18,
                "top_issuer_weight_proposed": 0.21,
                "top_issuer_weight_delta": 0.03,
                "coverage_status": "partial",
                "covered_position_count_current": 25,
                "covered_position_count_proposed": 27,
                "total_position_count_current": 30,
                "total_position_count_proposed": 31,
                "uncovered_position_count_current": 5,
                "uncovered_position_count_proposed": 4,
                "coverage_ratio_current": 0.833333,
                "coverage_ratio_proposed": 0.870968,
                "note": "issuer_id missing in lotus-core instrument_enrichment",
                "top_issuer_current": {
                    "issuer_id": "ULTIMATE_PIMCO",
                    "issuer_name": "Pacific Investment Management Company LLC",
                    "weight": 0.18,
                },
                "top_issuer_proposed": {
                    "issuer_id": "ULTIMATE_PIMCO",
                    "issuer_name": "Pacific Investment Management Company LLC",
                    "weight": 0.21,
                },
            }
        },
    )
    valuation_context: ConcentrationValuationContext | None = Field(
        default=None,
        description="Valuation context sourced from lotus-core for stateful/simulation mode.",
        json_schema_extra={
            "example": {
                "portfolio_currency": "EUR",
                "reporting_currency": "USD",
                "position_basis": "market_value_base",
                "weight_basis": "total_market_value_base",
            }
        },
    )
    metadata: ConcentrationMetadata | None = Field(
        default=None,
        description="Execution metadata for stateful/simulation concentration calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-27",
                "portfolio_id": "DEMO_DPM_EUR_001",
                "simulation_session_id": "SIM_0001",
                "simulation_session_version": 3,
                "session_expires_at": "2026-02-28T10:30:00Z",
                "issuer_grouping_level": "ultimate_parent",
                "enrichment_policy": "merge_caller_then_core",
                "include_cash_positions": True,
                "include_zero_quantity_positions": False,
            }
        },
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": cast(Any, CONCENTRATION_RESPONSE_EXAMPLES)}
    )
