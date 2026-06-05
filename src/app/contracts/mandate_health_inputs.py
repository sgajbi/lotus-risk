from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.risk import ReturnPoint, RiskRequestPeriod, RiskRequestScope


class MandateRiskHealthContextRequest(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier for the mandate health risk context.",
        json_schema_extra={"example": "PB_SG_GLOBAL_BAL_001"},
    )
    scope: RiskRequestScope = Field(
        description="Risk scope and as-of date used for source-owned mandate health evaluation.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-27",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    period: RiskRequestPeriod = Field(
        description="Single risk period evaluated for mandate health context.",
        json_schema_extra={"example": {"type": "YTD", "name": "YTD"}},
    )
    portfolio_open_date: dt.date = Field(
        description="Portfolio inception date used for SI period handling.",
        json_schema_extra={"example": "2024-01-01"},
    )
    returns: list[ReturnPoint] = Field(
        description="Portfolio return observations in percentage points.",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.25}]},
    )
    benchmark_returns: list[ReturnPoint] = Field(
        description="Benchmark return observations in percentage points.",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.18}]},
    )
    tracking_error_attention_threshold: Decimal = Field(
        default=Decimal("0.05"),
        ge=Decimal("0"),
        description=(
            "Annualized tracking-error attention threshold as a decimal ratio. "
            "For example, 0.05 represents 5 percent annualized tracking error."
        ),
        json_schema_extra={"example": "0.05"},
    )

    model_config = ConfigDict(extra="forbid")
