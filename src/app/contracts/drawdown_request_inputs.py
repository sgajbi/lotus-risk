from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.drawdown_common_inputs import (
    BenchmarkDrawdownPolicy,
    DrawdownAnalysisOptions,
    DrawdownInputMode,
)
from app.contracts.drawdown_examples import DRAWDOWN_REQUEST_EXAMPLES
from app.contracts.drawdown_stateful_inputs import DrawdownStatefulInput
from app.contracts.drawdown_stateless_inputs import DrawdownStatelessInput


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


__all__ = ["DrawdownAnalyticsRequest"]
