from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.drawdown_examples import DRAWDOWN_REQUEST_EXAMPLES
from app.contracts.risk import ReturnPoint, RiskRequestPeriod, RiskRequestScope


class DrawdownInputMode(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"


class BenchmarkDrawdownPolicy(BaseModel):
    include_benchmark: bool = Field(
        default=False,
        description="Whether benchmark-relative drawdown should be computed.",
        json_schema_extra={"example": False},
    )
    missing_benchmark_policy: Literal["IGNORE", "REQUIRE"] = Field(
        default="IGNORE",
        description="Behavior when benchmark drawdown is requested but benchmark series is unavailable.",
        json_schema_extra={"example": "IGNORE"},
    )


class DrawdownAnalysisOptions(BaseModel):
    include_underwater_series: bool = Field(
        default=False,
        description="Whether underwater drawdown time series points should be included in responses.",
        json_schema_extra={"example": False},
    )
    include_episode_list: bool = Field(
        default=True,
        description="Whether drawdown episodes should be returned in responses.",
        json_schema_extra={"example": True},
    )
    top_n_episodes: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of worst drawdown episodes to return per period.",
        json_schema_extra={"example": 5},
    )
    cdar_alpha: float = Field(
        default=0.95,
        description="Confidence level used for drawdown-at-risk and conditional drawdown-at-risk metrics.",
        json_schema_extra={"example": 0.95},
    )
    minimum_episode_depth_bps: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum episode depth (in basis points) required to include an episode in the list.",
        json_schema_extra={"example": 25.0},
    )
    duration_unit: Literal["BUSINESS_DAYS", "CALENDAR_DAYS"] = Field(
        default="BUSINESS_DAYS",
        description="Duration convention used for drawdown episode timing metrics.",
        json_schema_extra={"example": "BUSINESS_DAYS"},
    )

    @model_validator(mode="after")
    def validate_alpha(self) -> "DrawdownAnalysisOptions":
        allowed = {0.90, 0.95, 0.99}
        if self.cdar_alpha not in allowed:
            raise ValueError("cdar_alpha must be one of 0.90, 0.95, or 0.99")
        return self


def _validate_unique_period_names(periods: list[RiskRequestPeriod]) -> None:
    resolved_names = [period.name or period.type for period in periods]
    duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
    if duplicates:
        raise ValueError(
            "Duplicate period names resolved in request: "
            + ", ".join(duplicates)
            + ". Each period name (or type fallback) must be unique."
        )


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
    def validate_unique_period_names(self) -> "DrawdownStatelessInput":
        _validate_unique_period_names(self.periods)
        return self


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
        _validate_unique_period_names(self.periods)
        return self


class DrawdownAnalyticsRequest(BaseModel):
    input_mode: DrawdownInputMode = Field(
        default=DrawdownInputMode.STATELESS,
        description="Execution mode for drawdown analytics.",
        json_schema_extra={"example": "stateful"},
    )
    stateless_input: DrawdownStatelessInput | None = Field(
        default=None,
        description="Stateless drawdown input payload.",
        json_schema_extra={
            "example": {
                "scope": {
                    "as_of_date": "2026-03-31",
                    "reporting_currency": "USD",
                    "net_or_gross": "NET",
                },
                "periods": [{"type": "YTD", "name": "YTD"}],
                "returns": [
                    {"date": "2026-01-02", "value": 0.82},
                    {"date": "2026-01-03", "value": -1.45},
                    {"date": "2026-01-04", "value": 0.37},
                ],
                "benchmark_returns": [
                    {"date": "2026-01-02", "value": 0.61},
                    {"date": "2026-01-03", "value": -0.98},
                    {"date": "2026-01-04", "value": 0.21},
                ],
            }
        },
    )
    stateful_input: DrawdownStatefulInput | None = Field(
        default=None,
        description="Stateful drawdown input payload sourced through integrations.",
        json_schema_extra={
            "example": {
                "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                "as_of_date": "2026-03-31",
                "reporting_currency": "USD",
                "periods": [{"type": "YTD", "name": "YTD"}],
                "benchmark_policy": {
                    "include_benchmark": True,
                    "missing_benchmark_policy": "REQUIRE",
                },
            }
        },
    )
    benchmark_policy: BenchmarkDrawdownPolicy = Field(
        default_factory=BenchmarkDrawdownPolicy,
        description=(
            "Benchmark-relative drawdown policy for stateless requests. "
            "Stateful requests must use `stateful_input.benchmark_policy`."
        ),
        json_schema_extra={
            "example": {"include_benchmark": True, "missing_benchmark_policy": "REQUIRE"}
        },
    )
    analysis_options: DrawdownAnalysisOptions = Field(
        default_factory=DrawdownAnalysisOptions,
        description="Drawdown analytics option flags and thresholds.",
        json_schema_extra={
            "example": {
                "include_underwater_series": True,
                "include_episode_list": True,
                "top_n_episodes": 5,
                "cdar_alpha": 0.95,
                "minimum_episode_depth_bps": 25.0,
                "duration_unit": "BUSINESS_DAYS",
            }
        },
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": cast(Any, DRAWDOWN_REQUEST_EXAMPLES)},
    )

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "DrawdownAnalyticsRequest":
        if self.input_mode == DrawdownInputMode.STATELESS and self.stateless_input is None:
            raise ValueError("stateless_input is required when input_mode=stateless")
        if self.input_mode == DrawdownInputMode.STATEFUL and self.stateful_input is None:
            raise ValueError("stateful_input is required when input_mode=stateful")
        if (
            self.input_mode == DrawdownInputMode.STATEFUL
            and self.benchmark_policy.include_benchmark
        ):
            raise ValueError(
                "benchmark_policy is only supported for stateless drawdown requests; "
                "use stateful_input.benchmark_policy for input_mode=stateful"
            )
        return self
