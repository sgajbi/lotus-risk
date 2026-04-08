from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RiskMetric = Literal[
    "VOLATILITY",
    "DRAWDOWN",
    "SHARPE",
    "SORTINO",
    "BETA",
    "TRACKING_ERROR",
    "INFORMATION_RATIO",
    "VAR",
]


class RiskInputMode(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"


class RiskRequestScope(BaseModel):
    as_of_date: dt.date = Field(
        default_factory=dt.date.today,
        description="As-of date used for risk metric evaluation.",
        json_schema_extra={"example": "2025-03-31"},
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Optional reporting currency for normalized outputs.",
        json_schema_extra={"example": "USD"},
    )
    net_or_gross: Literal["NET", "GROSS"] = Field(
        default="NET",
        description="Whether returns represent net or gross performance.",
        json_schema_extra={"example": "NET"},
    )


class RiskRequestPeriod(BaseModel):
    type: Literal[
        "EXPLICIT",
        "YEAR",
        "MTD",
        "QTD",
        "YTD",
        "ONE_YEAR",
        "THREE_YEAR",
        "FIVE_YEAR",
        "SI",
    ] = Field(
        description="Period type used for metric aggregation.",
        json_schema_extra={"example": "EXPLICIT"},
    )
    name: str | None = Field(
        default=None,
        description="Optional display label for this period.",
        json_schema_extra={"example": "explicit_q1_2025"},
    )
    from_date: dt.date | None = Field(
        default=None,
        description="Explicit period start date (required when type=EXPLICIT).",
        json_schema_extra={"example": "2025-01-01"},
    )
    to_date: dt.date | None = Field(
        default=None,
        description="Explicit period end date (required when type=EXPLICIT).",
        json_schema_extra={"example": "2025-03-31"},
    )
    year: int | None = Field(
        default=None,
        description="Calendar year (required when type=YEAR).",
        json_schema_extra={"example": 2025},
    )

    @model_validator(mode="after")
    def validate_semantics(self) -> "RiskRequestPeriod":
        if self.type == "EXPLICIT" and (self.from_date is None or self.to_date is None):
            raise ValueError("EXPLICIT period requires from/to dates")
        if self.type == "YEAR" and self.year is None:
            raise ValueError("YEAR period requires year")
        return self


def _default_var_options() -> "VaROptions":
    return VaROptions.model_validate({})


def _default_risk_options() -> "RiskOptions":
    return RiskOptions.model_validate({})


class VaROptions(BaseModel):
    method: Literal["HISTORICAL", "GAUSSIAN", "CORNISH_FISHER"] = Field(
        default="HISTORICAL",
        description="Value-at-Risk calculation method.",
        json_schema_extra={"example": "HISTORICAL"},
    )
    confidence: float = Field(
        default=0.99,
        gt=0,
        lt=1,
        description="Confidence level used for Value-at-Risk.",
        json_schema_extra={"example": 0.95},
    )
    horizon_days: int = Field(
        default=1,
        gt=0,
        description="Time horizon (in days) used for VaR scaling.",
        json_schema_extra={"example": 1},
    )
    include_expected_shortfall: bool = Field(
        default=True,
        description="Whether expected shortfall should be included in VAR details.",
        json_schema_extra={"example": True},
    )


class RiskOptions(BaseModel):
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY"] = Field(
        default="DAILY",
        description="Return sampling frequency.",
        json_schema_extra={"example": "DAILY"},
    )
    annualization_factor: int | None = Field(
        default=None,
        description="Optional annualization factor override.",
        json_schema_extra={"example": 252},
    )
    use_log_returns: bool = Field(
        default=False,
        description="Whether to transform arithmetic returns to log returns.",
        json_schema_extra={"example": False},
    )
    risk_free_mode: Literal["ZERO", "ANNUAL_RATE"] = Field(
        default="ZERO",
        description="Risk-free rate mode used for Sharpe calculations.",
        json_schema_extra={"example": "ANNUAL_RATE"},
    )
    risk_free_annual_rate: float | None = Field(
        default=None,
        ge=0,
        description="Annualized risk-free rate when risk_free_mode=ANNUAL_RATE.",
        json_schema_extra={"example": 0.01},
    )
    mar_annual_rate: float = Field(
        default=0.0,
        ge=0,
        description="Annualized minimum acceptable return used for Sortino ratio.",
        json_schema_extra={"example": 0.0},
    )
    var: VaROptions = Field(
        default_factory=_default_var_options,
        description="Value-at-Risk options.",
        json_schema_extra={
            "example": {
                "method": "HISTORICAL",
                "confidence": 0.95,
                "horizon_days": 1,
                "include_expected_shortfall": True,
            }
        },
    )


class ReturnPoint(BaseModel):
    date: dt.date = Field(
        description="Date of return observation.",
        json_schema_extra={"example": "2025-01-02"},
    )
    value: float = Field(
        description="Return value in percentage points.",
        json_schema_extra={"example": 0.85},
    )


def _validate_unique_period_names(periods: list["RiskRequestPeriod"]) -> None:
    resolved_names = [period.name or period.type for period in periods]
    duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
    if duplicates:
        duplicate_names = ", ".join(duplicates)
        raise ValueError(
            f"Duplicate period names resolved in request: {duplicate_names}. "
            "Each period name (or type fallback) must be unique."
        )


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
        default_factory=_default_risk_options,
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
        _validate_unique_period_names(self.periods)
        return self


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
        default_factory=_default_risk_options,
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
        _validate_unique_period_names(self.periods)
        return self


class RiskAnalyticsRequest(BaseModel):
    input_mode: RiskInputMode = Field(
        default=RiskInputMode.STATELESS,
        description="Execution mode for risk analytics: stateless or stateful.",
        json_schema_extra={"example": "stateless"},
    )
    stateless_input: StatelessRiskInput | None = Field(
        default=None,
        description="Stateless execution payload with fully supplied return series.",
        json_schema_extra={
            "example": {
                "scope": {
                    "as_of_date": "2025-03-31",
                    "reporting_currency": "USD",
                    "net_or_gross": "NET",
                },
                "periods": [{"type": "YTD", "name": "YTD"}],
                "metrics": ["VOLATILITY", "VAR"],
                "portfolio_open_date": "2024-01-01",
                "returns": [{"date": "2025-01-02", "value": 0.8}],
            }
        },
    )
    stateful_input: StatefulRiskInput | None = Field(
        default=None,
        description="Stateful execution payload sourced from upstream integrations.",
        json_schema_extra={
            "example": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "reporting_currency": "USD",
                "client_id": "CLIENT_1000123",
            }
        },
    )
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "RiskAnalyticsRequest":
        if self.input_mode == RiskInputMode.STATELESS and self.stateless_input is None:
            raise ValueError("stateless_input is required when input_mode=stateless")

        if self.input_mode == RiskInputMode.STATEFUL and self.stateful_input is None:
            raise ValueError("stateful_input is required when input_mode=stateful")

        return self


# Alias retained to keep risk engine internals and tests stateless while request envelope evolves.
RiskStatelessCalculationInput = StatelessRiskInput
RiskCalculationRequest = StatelessRiskInput


class RiskValue(BaseModel):
    value: float | None = Field(
        default=None,
        description="Computed metric value.",
        json_schema_extra={"example": 0.1234},
    )
    details: dict[str, str | float | int | bool | None] | None = Field(
        default=None,
        description="Optional metric-specific details or deterministic error payload.",
        json_schema_extra={"example": {"error": "Insufficient data"}},
    )


class RiskPeriodResult(BaseModel):
    start_date: dt.date = Field(
        description="Resolved period start date after semantic normalization.",
        json_schema_extra={"example": "2025-01-01"},
    )
    end_date: dt.date = Field(
        description="Resolved period end date after semantic normalization.",
        json_schema_extra={"example": "2025-03-31"},
    )
    portfolio_observation_count: int = Field(
        default=0,
        description="Number of portfolio return observations used for this period result.",
        json_schema_extra={"example": 64},
    )
    benchmark_observation_count: int = Field(
        default=0,
        description="Number of benchmark return observations available for this period result.",
        json_schema_extra={"example": 64},
    )
    aligned_benchmark_observation_count: int = Field(
        default=0,
        description="Number of aligned portfolio/benchmark observations used for benchmark-dependent metrics.",
        json_schema_extra={"example": 61},
    )
    benchmark_context: dict[str, str | bool | int] | None = Field(
        default=None,
        description="Execution context for benchmark-dependent metrics in this period.",
        json_schema_extra={
            "example": {
                "requested": True,
                "available": True,
                "aligned": True,
                "reason": "APPLIED",
                "requested_metric_count": 3,
            }
        },
    )
    metrics: dict[str, RiskValue] = Field(
        description="Metric values keyed by metric name.",
        json_schema_extra={"example": {"VOLATILITY": {"value": 9.75}, "SHARPE": {"value": 2.61}}},
    )


class RiskFreeContext(BaseModel):
    requested: bool = Field(
        default=False,
        description="Whether any requested metrics depend on risk-free configuration.",
        json_schema_extra={"example": True},
    )
    applied: bool = Field(
        default=False,
        description="Whether risk-free configuration was applied to at least one requested metric.",
        json_schema_extra={"example": True},
    )
    reason: Literal["NOT_REQUESTED", "ZERO_RATE", "ANNUAL_RATE_APPLIED"] = Field(
        default="NOT_REQUESTED",
        description="Deterministic explanation of how risk-free configuration affected this response.",
        json_schema_extra={"example": "ANNUAL_RATE_APPLIED"},
    )
    periodic_rate: float = Field(
        default=0.0,
        description="Applied periodic risk-free rate as a decimal return after annualization.",
        json_schema_extra={"example": 0.00003949},
    )


class RiskResponseMetadata(BaseModel):
    contract_version: str = Field(
        default="v1",
        description="Risk analytics contract version.",
        json_schema_extra={"example": "v1"},
    )
    methodology_version: str = Field(
        default="risk.v1",
        description="Methodology version used for the risk engine.",
        json_schema_extra={"example": "risk.v1"},
    )
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY"] = Field(
        default="DAILY",
        description="Applied return sampling frequency.",
        json_schema_extra={"example": "DAILY"},
    )
    annualization_factor: int = Field(
        default=252,
        description="Applied annualization factor after defaults or overrides.",
        json_schema_extra={"example": 252},
    )
    use_log_returns: bool = Field(
        default=False,
        description="Whether returns were transformed to log returns before metric evaluation.",
        json_schema_extra={"example": False},
    )
    risk_free_mode: Literal["ZERO", "ANNUAL_RATE"] = Field(
        default="ZERO",
        description="Applied risk-free mode for Sharpe calculations.",
        json_schema_extra={"example": "ZERO"},
    )
    risk_free_annual_rate: float | None = Field(
        default=None,
        description="Applied annual risk-free rate when risk_free_mode=ANNUAL_RATE.",
        json_schema_extra={"example": 0.01},
    )
    risk_free_context: RiskFreeContext = Field(
        default_factory=RiskFreeContext,
        description="Applied risk-free interpretation context for Sharpe calculations.",
        json_schema_extra={
            "example": {
                "requested": True,
                "applied": True,
                "reason": "ANNUAL_RATE_APPLIED",
                "periodic_rate": 0.00003949,
            }
        },
    )
    mar_annual_rate: float = Field(
        default=0.0,
        description="Applied annual minimum acceptable return for Sortino calculations.",
        json_schema_extra={"example": 0.0},
    )
    var_method: Literal["HISTORICAL", "GAUSSIAN", "CORNISH_FISHER"] = Field(
        default="HISTORICAL",
        description="Applied Value-at-Risk method.",
        json_schema_extra={"example": "HISTORICAL"},
    )
    var_confidence: float = Field(
        default=0.99,
        description="Applied Value-at-Risk confidence level.",
        json_schema_extra={"example": 0.95},
    )
    var_horizon_days: int = Field(
        default=1,
        description="Applied Value-at-Risk horizon in business days.",
        json_schema_extra={"example": 1},
    )


class RiskResponse(BaseModel):
    scope: RiskRequestScope = Field(
        description="Echoed normalized scope context used for calculation.",
        json_schema_extra={
            "example": {
                "as_of_date": "2025-03-31",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    results: dict[str, RiskPeriodResult] = Field(
        description="Risk results keyed by period name or period type.",
        json_schema_extra={
            "example": {
                "explicit_q1_2025": {
                    "start_date": "2025-01-01",
                    "end_date": "2025-03-31",
                    "portfolio_observation_count": 64,
                    "benchmark_observation_count": 64,
                    "aligned_benchmark_observation_count": 61,
                    "benchmark_context": {
                        "requested": True,
                        "available": True,
                        "aligned": True,
                        "reason": "APPLIED",
                        "requested_metric_count": 3,
                    },
                    "metrics": {"VOLATILITY": {"value": 0.23}},
                }
            }
        },
    )
    metadata: RiskResponseMetadata = Field(
        default_factory=RiskResponseMetadata,
        description="Risk contract and applied option metadata.",
        json_schema_extra={
            "example": {
                "contract_version": "v1",
                "methodology_version": "risk.v1",
                "frequency": "DAILY",
                "annualization_factor": 252,
                "use_log_returns": False,
                "risk_free_mode": "ZERO",
                "risk_free_annual_rate": None,
                "risk_free_context": {
                    "requested": True,
                    "applied": True,
                    "reason": "ZERO_RATE",
                    "periodic_rate": 0.0,
                },
                "mar_annual_rate": 0.0,
                "var_method": "HISTORICAL",
                "var_confidence": 0.95,
                "var_horizon_days": 1,
            }
        },
    )
