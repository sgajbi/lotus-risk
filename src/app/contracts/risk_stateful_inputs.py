from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.risk_common_inputs import (
    RiskMetric,
    RiskRequestPeriod,
    validate_unique_period_names,
)
from app.contracts.risk_options import RiskOptions, default_risk_options


class StatefulRiskInput(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier resolved through lotus-core/lotus-performance integrations.",
        json_schema_extra={"example": "DEMO_DPM_EUR_001"},
    )
    as_of_date: dt.date = Field(
        description="Business date used to resolve time series inputs from upstream services.",
        json_schema_extra={"example": "2026-02-27"},
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Optional reporting currency override. Defaults to portfolio currency policy.",
        json_schema_extra={"example": "USD"},
    )
    client_id: str | None = Field(
        default=None,
        description="Optional client identifier used for upstream data access policy controls.",
        json_schema_extra={"example": "CLIENT_1000123"},
    )
    benchmark_id: str | None = Field(
        default=None,
        description=(
            "Optional benchmark override for benchmark-dependent stateful metrics. When omitted, "
            "lotus-performance resolves the portfolio benchmark assignment."
        ),
        json_schema_extra={"example": "BMK_PB_GLOBAL_BALANCED_60_40"},
    )
    net_or_gross: Literal["NET", "GROSS"] = Field(
        default="NET",
        description="Whether sourced returns are evaluated on net or gross basis.",
        json_schema_extra={"example": "NET"},
    )
    periods: list[RiskRequestPeriod] = Field(
        description="List of periods to evaluate for stateful execution.",
        json_schema_extra={
            "example": [{"type": "EXPLICIT", "from_date": "2025-01-01", "to_date": "2025-03-31"}]
        },
    )
    metrics: list[RiskMetric] = Field(
        description="Requested risk metrics for stateful execution.",
        json_schema_extra={"example": ["VOLATILITY", "SHARPE", "VAR"]},
    )
    options: RiskOptions = Field(
        default_factory=default_risk_options,
        description="Risk calculation options for stateful execution.",
        json_schema_extra={
            "example": {
                "frequency": "DAILY",
                "risk_free_mode": "ANNUAL_RATE",
                "risk_free_annual_rate": 0.01,
                "var": {
                    "method": "HISTORICAL",
                    "confidence": 0.95,
                    "horizon_days": 1,
                    "include_expected_shortfall": True,
                },
            }
        },
    )

    @model_validator(mode="after")
    def validate_unique_period_names(self) -> "StatefulRiskInput":
        validate_unique_period_names(self.periods)
        return self


__all__ = ["StatefulRiskInput"]
