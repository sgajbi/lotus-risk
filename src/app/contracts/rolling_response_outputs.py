from __future__ import annotations

import datetime as dt
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.audit import AuditMetadataFields
from app.contracts.risk import RiskCalculationSupportability, RiskRequestScope
from app.contracts.rolling_examples import ROLLING_RESPONSE_EXAMPLE
from app.contracts.rolling_inputs import RollingInputMode
from app.contracts.rolling_metric_outputs import (
    RollingBenchmarkContext,
    RollingRiskFreeContext,
    RollingWindowResult,
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
        json_schema_extra={
            "example": {
                "requested": True,
                "available": True,
                "aligned": True,
                "reason": "APPLIED",
            }
        },
    )
    risk_free_context: RollingRiskFreeContext = Field(
        description="Risk-free application context for rolling Sharpe in this period.",
        json_schema_extra={
            "example": {
                "requested": False,
                "available": False,
                "aligned": False,
                "reason": "NOT_REQUESTED",
            }
        },
    )
    window_results: list[RollingWindowResult] = Field(
        default_factory=list,
        description="Rolling window results for this period.",
        json_schema_extra={"example": [{"window_length": 63, "metric_summaries": {}}]},
    )
    quality_flags: list[str] = Field(
        default_factory=list,
        description="Deterministic quality/coverage flags for this period.",
        json_schema_extra={"example": ["metric:ROLLING_BETA:benchmark_variance_zero"]},
    )
    error: str | None = Field(
        default=None,
        description="Deterministic period-level error when rolling metrics cannot be computed.",
        json_schema_extra={"example": "Insufficient data"},
    )


class RollingRequestDependencyContext(BaseModel):
    requested: bool = Field(
        description="Whether this dependency family is required by any requested rolling metric.",
        json_schema_extra={"example": True},
    )
    requested_metrics: list[str] = Field(
        default_factory=list,
        description="Requested rolling metrics that depend on this family.",
        json_schema_extra={"example": ["ROLLING_BETA", "ROLLING_TRACKING_ERROR"]},
    )


class RollingMetadata(AuditMetadataFields):
    contract_version: str = Field(
        default="v1",
        description="Rolling metrics contract version.",
        json_schema_extra={"example": "v1"},
    )
    methodology_version: str = Field(
        default="rolling_metrics.v1",
        description="Methodology version used for rolling metric formulas.",
        json_schema_extra={"example": "rolling_metrics.v1"},
    )
    annualization_basis: int = Field(
        description="Annualization basis used for annualized rolling metrics.",
        json_schema_extra={"example": 252},
    )
    requested_metrics: list[str] = Field(
        default_factory=list,
        description="Requested rolling metrics in canonical execution order.",
        json_schema_extra={
            "example": [
                "ROLLING_VOLATILITY",
                "ROLLING_SHARPE",
                "ROLLING_BETA",
            ]
        },
    )
    window_lengths_requested: list[int] = Field(
        default_factory=list,
        description="Rolling window lengths requested for this response.",
        json_schema_extra={"example": [21, 63, 126]},
    )
    window_count_requested: int = Field(
        default=0,
        description="Number of rolling window lengths requested for this response.",
        json_schema_extra={"example": 3},
    )
    alignment_policy: Literal["INNER_JOIN"] = Field(
        description="Series alignment policy used for multi-series rolling metrics.",
        json_schema_extra={"example": "INNER_JOIN"},
    )
    min_observations_policy: Literal["STRICT", "ALLOW_PARTIAL"] = Field(
        description="Minimum-observations policy used across the requested rolling windows.",
        json_schema_extra={"example": "STRICT"},
    )
    include_time_series: bool = Field(
        description="Whether rolling metric time-series points were requested for emitted windows.",
        json_schema_extra={"example": False},
    )
    benchmark_context: RollingRequestDependencyContext = Field(
        description="Top-level benchmark dependency context derived from the requested rolling metrics.",
        json_schema_extra={
            "example": {
                "requested": True,
                "requested_metrics": [
                    "ROLLING_BETA",
                    "ROLLING_TRACKING_ERROR",
                ],
            }
        },
    )
    risk_free_context: RollingRequestDependencyContext = Field(
        description="Top-level risk-free dependency context derived from the requested rolling metrics.",
        json_schema_extra={
            "example": {
                "requested": True,
                "requested_metrics": ["ROLLING_SHARPE"],
            }
        },
    )
    calculation_supportability: RiskCalculationSupportability = Field(
        default_factory=lambda: RiskCalculationSupportability(
            state="ready",
            reason="calculation_complete",
            freshness_bucket="unknown",
        ),
        description="Source-backed supportability posture for UI and operator consumption.",
        json_schema_extra={
            "example": {
                "state": "ready",
                "reason": "calculation_complete",
                "freshness_bucket": "current",
                "degraded_metric_count": 0,
                "empty_period_count": 0,
                "evaluated_period_count": 1,
            }
        },
    )


class RollingResponse(BaseModel):
    source_service: Literal["lotus-risk"] = Field(
        default="lotus-risk",
        description="Service identifier producing this rolling analytics response.",
        json_schema_extra={"example": "lotus-risk"},
    )
    input_mode: RollingInputMode = Field(
        description="Execution mode used to produce this response.",
        json_schema_extra={"example": "stateless"},
    )
    scope: RiskRequestScope = Field(
        description="Normalized scope context used for rolling calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    results: dict[str, RollingPeriodResult] = Field(
        description="Rolling metric period results keyed by period name.",
        json_schema_extra={
            "example": {
                "YTD": {
                    "start_date": "2026-01-01",
                    "end_date": "2026-02-28",
                    "series_count": 41,
                    "benchmark_series_count": 41,
                    "aligned_benchmark_series_count": 41,
                    "window_lengths_requested": [21, 63],
                    "window_count_requested": 2,
                    "window_lengths_emitted": [21, 63],
                    "window_count_emitted": 2,
                    "benchmark_context": {
                        "requested": True,
                        "available": True,
                        "aligned": True,
                        "reason": "APPLIED",
                    },
                    "risk_free_series_count": 41,
                    "aligned_risk_free_series_count": 41,
                    "risk_free_context": {
                        "requested": True,
                        "available": True,
                        "aligned": True,
                        "reason": "APPLIED",
                    },
                    "window_results": [],
                    "quality_flags": [],
                    "error": None,
                }
            }
        },
    )
    metadata: RollingMetadata = Field(
        description="Rolling metric contract and methodology metadata.",
        json_schema_extra={
            "example": {
                "contract_version": "v1",
                "methodology_version": "rolling_metrics.v1",
                "annualization_basis": 252,
                "requested_metrics": [
                    "ROLLING_VOLATILITY",
                    "ROLLING_BETA",
                    "ROLLING_TRACKING_ERROR",
                ],
                "window_lengths_requested": [21, 63],
                "window_count_requested": 2,
                "alignment_policy": "INNER_JOIN",
                "min_observations_policy": "STRICT",
                "include_time_series": False,
                "benchmark_context": {
                    "requested": True,
                    "requested_metrics": [
                        "ROLLING_BETA",
                        "ROLLING_TRACKING_ERROR",
                    ],
                },
                "risk_free_context": {
                    "requested": False,
                    "requested_metrics": [],
                },
            }
        },
    )

    model_config = ConfigDict(json_schema_extra={"example": cast(Any, ROLLING_RESPONSE_EXAMPLE)})
