from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.contracts.rolling_metric_outputs import (
    RollingBenchmarkContext,
    RollingRiskFreeContext,
    RollingWindowResult,
)
from app.contracts.rolling_period_field_examples import (
    ROLLING_PERIOD_BENCHMARK_CONTEXT_EXAMPLE,
    ROLLING_PERIOD_QUALITY_FLAGS_EXAMPLE,
    ROLLING_PERIOD_RISK_FREE_CONTEXT_EXAMPLE,
    ROLLING_PERIOD_WINDOW_RESULTS_EXAMPLE,
)


class RollingPeriodResult(BaseModel):
    start_date: dt.date = Field(
        description="Resolved period start date.",
        json_schema_extra={"example": "2026-01-01"},
    )
    end_date: dt.date = Field(
        description="Resolved period end date.",
        json_schema_extra={"example": "2026-02-28"},
    )
    series_count: int = Field(
        description="Number of portfolio return observations used in this period.",
        json_schema_extra={"example": 41},
    )
    benchmark_series_count: int = Field(
        default=0,
        description="Number of benchmark return observations available in this period.",
        json_schema_extra={"example": 41},
    )
    aligned_benchmark_series_count: int = Field(
        default=0,
        description="Number of aligned portfolio/benchmark observations available for benchmark-dependent rolling metrics.",
        json_schema_extra={"example": 41},
    )
    risk_free_series_count: int = Field(
        default=0,
        description="Number of risk-free observations available in this period.",
        json_schema_extra={"example": 41},
    )
    aligned_risk_free_series_count: int = Field(
        default=0,
        description="Number of aligned portfolio/risk-free observations available for rolling Sharpe.",
        json_schema_extra={"example": 41},
    )
    window_lengths_requested: list[int] = Field(
        default_factory=list,
        description="Rolling window lengths requested for this period.",
        json_schema_extra={"example": [21, 63]},
    )
    window_count_requested: int = Field(
        default=0,
        description="Number of rolling window lengths requested for this period.",
        json_schema_extra={"example": 2},
    )
    window_lengths_emitted: list[int] = Field(
        default_factory=list,
        description="Rolling window lengths actually emitted in this period result.",
        json_schema_extra={"example": [21, 63]},
    )
    window_count_emitted: int = Field(
        default=0,
        description="Number of rolling window lengths actually emitted in this period result.",
        json_schema_extra={"example": 2},
    )
    benchmark_context: RollingBenchmarkContext = Field(
        description="Benchmark application context for benchmark-dependent rolling metrics in this period.",
        json_schema_extra={"example": ROLLING_PERIOD_BENCHMARK_CONTEXT_EXAMPLE},
    )
    risk_free_context: RollingRiskFreeContext = Field(
        description="Risk-free application context for rolling Sharpe in this period.",
        json_schema_extra={"example": ROLLING_PERIOD_RISK_FREE_CONTEXT_EXAMPLE},
    )
    window_results: list[RollingWindowResult] = Field(
        default_factory=list,
        description="Rolling window results for this period.",
        json_schema_extra={"example": ROLLING_PERIOD_WINDOW_RESULTS_EXAMPLE},
    )
    quality_flags: list[str] = Field(
        default_factory=list,
        description="Deterministic quality/coverage flags for this period.",
        json_schema_extra={"example": ROLLING_PERIOD_QUALITY_FLAGS_EXAMPLE},
    )
    error: str | None = Field(
        default=None,
        description="Deterministic period-level error when rolling metrics cannot be computed.",
        json_schema_extra={"example": "Insufficient data"},
    )


__all__ = ["RollingPeriodResult"]
