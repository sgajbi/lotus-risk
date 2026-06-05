from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


def _default_var_options() -> "VaROptions":
    return VaROptions.model_validate({})


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


def default_risk_options() -> RiskOptions:
    return RiskOptions.model_validate({})


__all__ = [
    "RiskOptions",
    "VaROptions",
    "default_risk_options",
]
