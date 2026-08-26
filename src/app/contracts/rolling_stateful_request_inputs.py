from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.risk import RiskRequestPeriod
from app.contracts.rolling_common_inputs import (
    ROLLING_MAX_PERIODS,
    RollingOptions,
    validate_unique_period_names,
)


class RollingStatefulInput(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier resolved through lotus-performance integration contracts.",
        json_schema_extra={"example": "DEMO_DPM_EUR_001"},
    )
    as_of_date: dt.date = Field(
        description="Business date used for upstream series sourcing.",
        json_schema_extra={"example": "2026-02-28"},
    )
    client_id: str | None = Field(
        default=None,
        description="Optional client identifier for policy-controlled upstream access.",
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
        description="List of periods to evaluate rolling metrics.",
        max_length=ROLLING_MAX_PERIODS,
        json_schema_extra={"example": [{"type": "YTD", "name": "YTD"}]},
    )
    rolling_options: RollingOptions = Field(
        default_factory=RollingOptions,
        description="Rolling metric configuration options.",
        json_schema_extra={
            "example": {
                "window_lengths": [21, 63, 126],
                "metrics": ["ROLLING_VOLATILITY", "ROLLING_MAX_DRAWDOWN"],
                "annualization_basis": 252,
                "min_observations_policy": "STRICT",
                "alignment_policy": "INNER_JOIN",
                "include_time_series": False,
            }
        },
    )

    @model_validator(mode="after")
    def validate_semantics(self) -> RollingStatefulInput:
        validate_unique_period_names(self.periods)
        return self


__all__ = ["RollingStatefulInput"]
