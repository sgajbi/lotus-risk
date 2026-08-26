from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.attribution_common_inputs import (
    AttributionOptions,
    validate_unique_period_names,
)
from app.contracts.risk import RiskRequestPeriod


class HistoricalAttributionStatefulInput(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier resolved through stateful integrations.",
        json_schema_extra={"example": "DEMO_DPM_EUR_001"},
    )
    as_of_date: dt.date = Field(
        description="Business date used for stateful sourcing.",
        json_schema_extra={"example": "2026-02-28"},
    )
    client_id: str | None = Field(
        default=None,
        description="Optional client identifier for policy-controlled upstream sourcing.",
        json_schema_extra={"example": "CLIENT_1000123"},
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Optional reporting currency override.",
        json_schema_extra={"example": "USD"},
    )
    net_or_gross: Literal["NET", "GROSS"] = Field(
        default="NET",
        description="Whether sourced returns are net or gross.",
        json_schema_extra={"example": "NET"},
    )
    periods: list[RiskRequestPeriod] = Field(
        description="List of periods to evaluate historical attribution.",
        json_schema_extra={"example": [{"type": "YTD", "name": "YTD"}]},
    )
    attribution_options: AttributionOptions = Field(
        default_factory=AttributionOptions,
        description="Historical attribution options for stateful execution.",
        json_schema_extra={
            "example": {
                "attribution_types": ["TOTAL_RISK"],
                "metrics": ["VOLATILITY"],
                "grouping_dimensions": ["SECTOR"],
            }
        },
    )

    @model_validator(mode="after")
    def validate_semantics(self) -> HistoricalAttributionStatefulInput:
        validate_unique_period_names(self.periods)

        grouping_dimensions = self.attribution_options.grouping_dimensions
        if "CUSTOM" in grouping_dimensions:
            raise ValueError(
                "stateful historical-attribution does not support grouping_dimension=CUSTOM"
            )

        return self


__all__ = ["HistoricalAttributionStatefulInput"]
