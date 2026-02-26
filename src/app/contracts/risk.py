from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class RiskRequestScope(BaseModel):
    as_of_date: date = Field(default_factory=date.today, alias="asOfDate")
    reporting_currency: str | None = Field(default=None, alias="reportingCurrency")
    net_or_gross: Literal["NET", "GROSS"] = Field("NET", alias="netOrGross")


class RiskRequestPeriod(BaseModel):
    type: Literal["YTD", "MTD", "QTD", "ONE_YEAR", "THREE_YEAR", "SI", "CUSTOM", "YEAR"]
    name: str | None = None
    from_date: date | None = Field(default=None, alias="fromDate")
    to_date: date | None = Field(default=None, alias="toDate")
    year: int | None = None


class VaROptions(BaseModel):
    method: Literal["HISTORICAL", "GAUSSIAN", "CORNISH_FISHER"] = "HISTORICAL"
    confidence: float = Field(0.99, gt=0, lt=1)
    horizon_days: int = Field(1, gt=0, alias="horizonDays")
    include_expected_shortfall: bool = Field(True, alias="includeExpectedShortfall")


class RiskOptions(BaseModel):
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY"] = "DAILY"
    annualization_factor: int | None = Field(default=None, alias="annualizationFactor")
    use_log_returns: bool = Field(False, alias="useLogReturns")
    risk_free_mode: Literal["ZERO", "ANNUAL_RATE"] = Field("ZERO", alias="riskFreeMode")
    risk_free_annual_rate: float | None = Field(default=None, ge=0, alias="riskFreeAnnualRate")
    mar_annual_rate: float = Field(0.0, ge=0, alias="marAnnualRate")
    benchmark_security_id: str | None = Field(default=None, alias="benchmarkSecurityId")
    var: VaROptions = Field(default_factory=VaROptions)


class ReturnPoint(BaseModel):
    date: date
    value: float


class RiskCalculationRequest(BaseModel):
    scope: RiskRequestScope
    periods: list[RiskRequestPeriod]
    metrics: list[
        Literal[
            "VOLATILITY",
            "DRAWDOWN",
            "SHARPE",
            "SORTINO",
            "BETA",
            "TRACKING_ERROR",
            "INFORMATION_RATIO",
            "VAR",
        ]
    ]
    options: RiskOptions = Field(default_factory=RiskOptions)
    portfolio_open_date: date = Field(alias="portfolioOpenDate")
    returns: list[ReturnPoint]
    benchmark_returns: list[ReturnPoint] = Field(default_factory=list, alias="benchmarkReturns")


class RiskValue(BaseModel):
    value: float | None = None
    details: dict[str, Any] | None = None


class RiskPeriodResult(BaseModel):
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    metrics: dict[str, RiskValue]


class RiskResponse(BaseModel):
    scope: RiskRequestScope
    results: dict[str, RiskPeriodResult]
