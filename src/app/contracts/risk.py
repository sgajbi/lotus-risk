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
    SIMULATION = "simulation"


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
        resolved_names = [period.name or period.type for period in self.periods]
        duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
        if duplicates:
            duplicate_names = ", ".join(duplicates)
            raise ValueError(
                f"Duplicate period names resolved in request: {duplicate_names}. "
                "Each period name (or type fallback) must be unique."
            )
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
    cif_id: str | None = Field(
        default=None,
        description="Optional client identifier used for upstream data access policy controls.",
        json_schema_extra={"example": "CIF_1000123"},
    )


class SimulationRiskInput(StatefulRiskInput):
    session_id: str | None = Field(
        default=None,
        description="Optional existing simulation session identifier for iterative workflows.",
        json_schema_extra={"example": "SIM_0001"},
    )
    start_new_session: bool = Field(
        default=False,
        description="When true, forces lotus-risk to create a new simulation session.",
        json_schema_extra={"example": False},
    )
    session_ttl_hours: int | None = Field(
        default=None,
        ge=1,
        le=168,
        description="Optional simulation session TTL in hours when creating a new session.",
        json_schema_extra={"example": 24},
    )
    expected_version: int | None = Field(
        default=None,
        ge=1,
        description="Optional optimistic-lock version when reading simulation state.",
        json_schema_extra={"example": 3},
    )
    simulation_changes: list[dict[str, object]] = Field(
        default_factory=list,
        description="Simulation delta set. Not implemented for risk/calculate in this slice.",
        json_schema_extra={"example": [{"security_id": "SEC_A", "transaction_type": "BUY"}]},
    )


class RiskAnalyticsRequest(BaseModel):
    input_mode: RiskInputMode = Field(
        default=RiskInputMode.STATELESS,
        description="Execution mode for risk analytics: stateless, stateful, or simulation.",
        json_schema_extra={"example": "stateless"},
    )
    stateless_input: StatelessRiskInput | None = Field(
        default=None,
        description="Stateless execution payload with fully supplied return series.",
        json_schema_extra={
            "example": {
                "scope": {"as_of_date": "2025-03-31", "reporting_currency": "USD", "net_or_gross": "NET"},
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
                "cif_id": "CIF_1000123",
            }
        },
    )
    simulation_input: SimulationRiskInput | None = Field(
        default=None,
        description="Simulation execution payload. Reserved for a future slice.",
        json_schema_extra={
            "example": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "session_id": "SIM_0001",
                "simulation_changes": [{"security_id": "SEC_A", "transaction_type": "BUY"}],
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

        if self.input_mode == RiskInputMode.SIMULATION and self.simulation_input is None:
            raise ValueError("simulation_input is required when input_mode=simulation")

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
    metrics: dict[str, RiskValue] = Field(
        description="Metric values keyed by metric name.",
        json_schema_extra={"example": {"VOLATILITY": {"value": 0.23}}},
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
                    "metrics": {"VOLATILITY": {"value": 0.23}},
                }
            }
        },
    )
