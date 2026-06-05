from __future__ import annotations

from pydantic import BaseModel, Field


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


__all__ = ["ConcentrationValuationContext"]
