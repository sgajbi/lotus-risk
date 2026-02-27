from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _coalesce_period_boundaries(values: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(values)
    normalized["fromDate"] = (
        values.get("fromDate")
        or values.get("from_date")
        or values.get("from")
        or values.get("start")
    )
    normalized["toDate"] = (
        values.get("toDate") or values.get("to_date") or values.get("to") or values.get("end")
    )
    return normalized


def _normalize_period_type(raw_period_type: str) -> str:
    aliases = {
        "CUSTOM": "EXPLICIT",
        "ONE_YEAR": "ONE_YEAR",
        "1Y": "ONE_YEAR",
        "THREE_YEAR": "THREE_YEAR",
        "3Y": "THREE_YEAR",
        "FIVE_YEAR": "FIVE_YEAR",
        "5Y": "FIVE_YEAR",
    }
    period_type = (raw_period_type or "").strip().upper()
    return aliases.get(period_type, period_type)


class RiskRequestScope(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    as_of_date: date = Field(default_factory=date.today, alias="asOfDate")
    reporting_currency: str | None = Field(default=None, alias="reportingCurrency")
    net_or_gross: Literal["NET", "GROSS"] = Field("NET", alias="netOrGross")


class RiskRequestPeriod(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

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
    ]
    name: str | None = None
    from_date: date | None = Field(default=None, alias="fromDate")
    to_date: date | None = Field(default=None, alias="toDate")
    year: int | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, values: dict[str, Any]) -> dict[str, Any]:
        normalized = _coalesce_period_boundaries(values)
        raw_type = str(normalized.get("type", ""))
        normalized["type"] = _normalize_period_type(raw_type)
        return normalized

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
    model_config = ConfigDict(populate_by_name=True)

    method: Literal["HISTORICAL", "GAUSSIAN", "CORNISH_FISHER"] = "HISTORICAL"
    confidence: float = Field(0.99, gt=0, lt=1)
    horizon_days: int = Field(1, gt=0, alias="horizonDays")
    include_expected_shortfall: bool = Field(True, alias="includeExpectedShortfall")


class RiskOptions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    frequency: Literal["DAILY", "WEEKLY", "MONTHLY"] = "DAILY"
    annualization_factor: int | None = Field(default=None, alias="annualizationFactor")
    use_log_returns: bool = Field(False, alias="useLogReturns")
    risk_free_mode: Literal["ZERO", "ANNUAL_RATE"] = Field("ZERO", alias="riskFreeMode")
    risk_free_annual_rate: float | None = Field(default=None, ge=0, alias="riskFreeAnnualRate")
    mar_annual_rate: float = Field(0.0, ge=0, alias="marAnnualRate")
    var: VaROptions = Field(default_factory=_default_var_options)


class ReturnPoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: date
    value: float


class RiskCalculationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

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
    options: RiskOptions = Field(default_factory=_default_risk_options)
    portfolio_open_date: date = Field(alias="portfolioOpenDate")
    returns: list[ReturnPoint]
    benchmark_returns: list[ReturnPoint] = Field(default_factory=list, alias="benchmarkReturns")


class RiskValue(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    value: float | None = None
    details: dict[str, Any] | None = None


class RiskPeriodResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    metrics: dict[str, RiskValue]


class RiskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scope: RiskRequestScope
    results: dict[str, RiskPeriodResult]
