from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator

from app.contracts.risk_common_inputs import (
    ReturnPoint,
    RiskMetric,
    RiskRequestPeriod,
    RiskRequestScope,
    validate_unique_period_names,
)
from app.contracts.risk_options import RiskOptions, default_risk_options


class StatelessRiskInput(BaseModel):
    scope: RiskRequestScope = Field(
        description="Scope and policy context for risk calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2025-03-31",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    periods: list[RiskRequestPeriod] = Field(
        description="List of periods to evaluate.",
        json_schema_extra={
            "example": [{"type": "EXPLICIT", "from_date": "2025-01-01", "to_date": "2025-03-31"}]
        },
    )
    metrics: list[RiskMetric] = Field(
        description="Requested risk metrics.",
        json_schema_extra={"example": ["VOLATILITY", "SHARPE", "VAR"]},
    )
    options: RiskOptions = Field(
        default_factory=default_risk_options,
        description="Risk calculation options.",
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
    portfolio_open_date: dt.date = Field(
        description="Portfolio inception date used for SI period handling.",
        json_schema_extra={"example": "2024-01-01"},
    )
    returns: list[ReturnPoint] = Field(
        description="Portfolio return observations.",
        json_schema_extra={"example": [{"date": "2025-01-02", "value": 1.0}]},
    )
    benchmark_returns: list[ReturnPoint] = Field(
        default_factory=list,
        description="Benchmark return observations for benchmark-dependent metrics.",
        json_schema_extra={"example": [{"date": "2025-01-02", "value": 0.75}]},
    )

    @model_validator(mode="after")
    def validate_unique_period_names(self) -> "StatelessRiskInput":
        validate_unique_period_names(self.periods)
        return self


RiskStatelessCalculationInput = StatelessRiskInput
RiskCalculationRequest = StatelessRiskInput


__all__ = [
    "RiskCalculationRequest",
    "RiskStatelessCalculationInput",
    "StatelessRiskInput",
]
