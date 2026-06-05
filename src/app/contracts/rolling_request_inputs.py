from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.rolling_common_inputs import RollingInputMode
from app.contracts.rolling_stateful_request_inputs import RollingStatefulInput
from app.contracts.rolling_stateless_inputs import RollingStatelessInput


class RollingAnalyticsRequest(BaseModel):
    input_mode: RollingInputMode = Field(
        default=RollingInputMode.STATELESS,
        description="Execution mode for rolling risk analytics.",
        json_schema_extra={"example": "stateless"},
    )
    stateless_input: RollingStatelessInput | None = Field(
        default=None,
        description="Stateless payload with fully supplied return series.",
        json_schema_extra={
            "example": {
                "scope": {"as_of_date": "2026-02-28", "net_or_gross": "NET"},
                "periods": [{"type": "YTD", "name": "YTD"}],
                "returns": [{"date": "2026-01-02", "value": 0.45}],
                "benchmark_returns": [{"date": "2026-01-02", "value": 0.32}],
                "risk_free_returns": [{"date": "2026-01-02", "value": 0.01}],
            }
        },
    )
    stateful_input: RollingStatefulInput | None = Field(
        default=None,
        description=(
            "Stateful payload sourced through lotus-performance for portfolio/benchmark returns "
            "and lotus-core for risk-free reference series when rolling Sharpe is requested."
        ),
        json_schema_extra={
            "example": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-28",
                "periods": [{"type": "YTD", "name": "YTD"}],
                "rolling_options": {
                    "window_lengths": [21, 63],
                    "metrics": [
                        "ROLLING_VOLATILITY",
                        "ROLLING_BETA",
                        "ROLLING_TRACKING_ERROR",
                    ],
                    "annualization_basis": 252,
                    "min_observations_policy": "STRICT",
                    "alignment_policy": "INNER_JOIN",
                    "include_time_series": False,
                },
            }
        },
    )
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "RollingAnalyticsRequest":
        if self.input_mode == RollingInputMode.STATELESS and self.stateless_input is None:
            raise ValueError("stateless_input is required when input_mode=stateless")
        if self.input_mode == RollingInputMode.STATEFUL and self.stateful_input is None:
            raise ValueError("stateful_input is required when input_mode=stateful")
        return self


__all__ = ["RollingAnalyticsRequest"]
