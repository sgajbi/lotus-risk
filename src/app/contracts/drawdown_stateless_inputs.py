from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.contracts.drawdown_common_inputs import validate_unique_period_names
from app.contracts.risk import ReturnPoint, RiskRequestPeriod, RiskRequestScope


class DrawdownStatelessInput(BaseModel):
    scope: RiskRequestScope = Field(
        description="Scope and policy context for drawdown calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    periods: list[RiskRequestPeriod] = Field(
        description="List of periods to evaluate drawdown analytics.",
        json_schema_extra={"example": [{"type": "YTD", "name": "YTD"}]},
    )
    returns: list[ReturnPoint] = Field(
        description="Portfolio return observations in percentage points.",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": -0.6}]},
    )
    benchmark_returns: list[ReturnPoint] = Field(
        default_factory=list,
        description="Optional benchmark return observations in percentage points.",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": -0.4}]},
    )

    @model_validator(mode="after")
    def validate_unique_period_names(self) -> DrawdownStatelessInput:
        validate_unique_period_names(self.periods)
        return self


__all__ = ["DrawdownStatelessInput"]
