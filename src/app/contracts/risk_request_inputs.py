from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.risk_common_inputs import RiskInputMode
from app.contracts.risk_stateful_inputs import StatefulRiskInput
from app.contracts.risk_stateless_inputs import StatelessRiskInput


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
                "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
                "periods": [{"type": "YTD", "name": "YTD"}],
                "metrics": ["VOLATILITY", "BETA", "TRACKING_ERROR", "INFORMATION_RATIO"],
                "options": {
                    "frequency": "DAILY",
                    "risk_free_mode": "ZERO",
                    "mar_annual_rate": 0.0,
                    "var": {
                        "method": "HISTORICAL",
                        "confidence": 0.95,
                        "horizon_days": 4,
                        "include_expected_shortfall": True,
                    },
                },
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


__all__ = ["RiskAnalyticsRequest"]
