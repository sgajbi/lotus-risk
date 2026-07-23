from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.drawdown_common_inputs import (
    BenchmarkDrawdownPolicy,
    validate_unique_period_names,
)
from app.contracts.risk import RiskRequestPeriod


class DrawdownStatefulInput(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier resolved via lotus-performance and lotus-core integrations.",
        json_schema_extra={"example": "DEMO_DPM_EUR_001"},
    )
    as_of_date: dt.date = Field(
        description="Business date used to resolve historical return series.",
        json_schema_extra={"example": "2026-02-28"},
    )
    client_id: str | None = Field(
        default=None,
        description="Optional client identifier used for upstream data access controls.",
        json_schema_extra={"example": "CLIENT_1000123"},
    )
    benchmark_id: str | None = Field(
        default=None,
        description=(
            "Optional benchmark identifier used when benchmark-relative drawdown is requested. "
            "Set this with benchmark_policy.include_benchmark=true to avoid default benchmark drift."
        ),
        json_schema_extra={"example": "BMK_PB_GLOBAL_BALANCED_60_40"},
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Optional reporting currency override.",
        json_schema_extra={"example": "USD"},
    )
    net_or_gross: Literal["NET", "GROSS"] = Field(
        default="NET",
        description="Whether sourced returns should be net or gross.",
        json_schema_extra={"example": "NET"},
    )
    periods: list[RiskRequestPeriod] = Field(
        description="List of periods to evaluate drawdown analytics.",
        json_schema_extra={"example": [{"type": "YTD", "name": "YTD"}]},
    )
    benchmark_policy: BenchmarkDrawdownPolicy = Field(
        default_factory=BenchmarkDrawdownPolicy,
        description="Benchmark-relative drawdown policy configuration.",
        json_schema_extra={
            "example": {"include_benchmark": False, "missing_benchmark_policy": "IGNORE"}
        },
    )

    @model_validator(mode="after")
    def validate_unique_period_names(self) -> "DrawdownStatefulInput":
        validate_unique_period_names(self.periods)
        return self


__all__ = ["DrawdownStatefulInput"]
