from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.drawdown_common_inputs import (
    BenchmarkDrawdownPolicy,
    DrawdownAnalysisOptions,
    DrawdownInputMode,
)
from app.contracts.drawdown_examples import DRAWDOWN_REQUEST_EXAMPLES
from app.contracts.drawdown_request_field_examples import (
    DRAWDOWN_ANALYSIS_OPTIONS_EXAMPLE,
    DRAWDOWN_BENCHMARK_POLICY_EXAMPLE,
    DRAWDOWN_STATEFUL_INPUT_EXAMPLE,
    DRAWDOWN_STATELESS_INPUT_EXAMPLE,
)
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
        json_schema_extra={"example": DRAWDOWN_STATELESS_INPUT_EXAMPLE},
    )
    stateful_input: DrawdownStatefulInput | None = Field(
        default=None,
        description="Stateful drawdown input payload sourced through integrations.",
        json_schema_extra={"example": DRAWDOWN_STATEFUL_INPUT_EXAMPLE},
    )
    benchmark_policy: BenchmarkDrawdownPolicy = Field(
        default_factory=BenchmarkDrawdownPolicy,
        description=(
            "Benchmark-relative drawdown policy for stateless requests. "
            "Stateful requests must use `stateful_input.benchmark_policy`."
        ),
        json_schema_extra={"example": DRAWDOWN_BENCHMARK_POLICY_EXAMPLE},
    )
    analysis_options: DrawdownAnalysisOptions = Field(
        default_factory=DrawdownAnalysisOptions,
        description="Drawdown analytics option flags and thresholds.",
        json_schema_extra={"example": DRAWDOWN_ANALYSIS_OPTIONS_EXAMPLE},
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": cast(Any, DRAWDOWN_REQUEST_EXAMPLES)},
    )

    @model_validator(mode="after")
    def normalize_and_validate(self) -> DrawdownAnalyticsRequest:
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
