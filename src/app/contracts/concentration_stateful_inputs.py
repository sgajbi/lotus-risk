from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.contracts.concentration_common_inputs import IssuerMappingInput


class StatefulConcentrationInput(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier resolved through lotus-core.",
        json_schema_extra={"example": "DEMO_DPM_EUR_001"},
    )
    as_of_date: date = Field(
        description="Business date used to resolve baseline positions from lotus-core.",
        json_schema_extra={"example": "2026-02-27"},
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Optional reporting currency override. Defaults to portfolio currency.",
        json_schema_extra={"example": "USD"},
    )
    include_cash_positions: bool = Field(
        default=True,
        description="Whether cash-class positions are included in concentration inputs.",
        json_schema_extra={"example": True},
    )
    include_zero_quantity_positions: bool = Field(
        default=False,
        description="Whether zero-quantity positions are included in concentration inputs.",
        json_schema_extra={"example": False},
    )
    top_n: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Top-N bucket used for single-position concentration aggregates.",
        json_schema_extra={"example": 10},
    )
    issuer_mappings: list[IssuerMappingInput] = Field(
        default_factory=list,
        description=(
            "Optional caller-provided issuer mappings keyed by security_id. "
            "Used according to enrichment_policy when computing issuer concentration."
        ),
        json_schema_extra={
            "example": [
                {
                    "security_id": "SEC_AAPL_US",
                    "issuer_id": "ISSUER_APPLE_INC",
                    "issuer_name": "Apple Inc.",
                    "ultimate_parent_issuer_id": "ISSUER_APPLE_HOLDING",
                    "ultimate_parent_issuer_name": "Apple Holdings PLC",
                }
            ]
        },
    )


__all__ = ["StatefulConcentrationInput"]
