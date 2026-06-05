from __future__ import annotations

import datetime as dt
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.audit import AuditMetadataFields
from app.contracts.risk import RiskCalculationSupportability, RiskRequestScope
from app.contracts.rolling_examples import ROLLING_RESPONSE_EXAMPLE
from app.contracts.rolling_inputs import RollingInputMode


class RollingMetricSummary(BaseModel):
    total_point_count: int = Field(
        default=0,
        description="Total rolling observation slots evaluated for this metric/window, including null warm-up periods.",
        json_schema_extra={"example": 64},
    )
    computed_point_count: int = Field(
        default=0,
        description="Number of rolling observations that produced non-null values for this metric/window.",
        json_schema_extra={"example": 44},
    )
    coverage_ratio: float = Field(
        default=0.0,
        description="Computed-point coverage ratio for this metric/window (`computed_point_count / total_point_count`).",
        json_schema_extra={"example": 0.6875},
    )
    min_observations_required: int = Field(
        default=0,
        description="Minimum observations required before this rolling metric/window can emit non-null values.",
        json_schema_extra={"example": 21},
    )
    warmup_point_count: int = Field(
        default=0,
        description="Expected leading warm-up slots before the rolling window reaches minimum observations.",
        json_schema_extra={"example": 20},
    )
    non_computed_point_count: int = Field(
        default=0,
        description="Total slots that did not produce a rolling value for this metric/window.",
        json_schema_extra={"example": 20},
    )
    post_warmup_gap_point_count: int = Field(
        default=0,
        description="Non-computed slots beyond expected warm-up, indicating additional data/alignment gaps.",
        json_schema_extra={"example": 0},
    )
    latest_observation_date: dt.date | None = Field(
        default=None,
        description="Date of the latest non-null rolling metric value included in this summary.",
        json_schema_extra={"example": "2026-03-31"},
    )
    latest: float | None = Field(
        default=None,
        description="Latest rolling metric value in decimal units for this period/window.",
        json_schema_extra={"example": 0.1374},
    )
    average: float | None = Field(
        default=None,
        description="Average rolling metric value over the period/window.",
        json_schema_extra={"example": 0.1221},
    )
    minimum: float | None = Field(
        default=None,
        description="Minimum rolling metric value over the period/window.",
        json_schema_extra={"example": 0.0913},
    )
    maximum: float | None = Field(
        default=None,
        description="Maximum rolling metric value over the period/window.",
        json_schema_extra={"example": 0.1662},
    )
    p05: float | None = Field(
        default=None,
        description="5th percentile rolling metric value over the period/window.",
        json_schema_extra={"example": 0.0975},
    )
    p50: float | None = Field(
        default=None,
        description="50th percentile rolling metric value over the period/window.",
        json_schema_extra={"example": 0.1218},
    )
    p95: float | None = Field(
        default=None,
        description="95th percentile rolling metric value over the period/window.",
        json_schema_extra={"example": 0.1611},
    )


class RollingMetricSeriesPoint(BaseModel):
    date: dt.date = Field(
        description="Observation date for rolling metric values.",
        json_schema_extra={"example": "2026-02-28"},
    )
    metric_values: dict[str, float | None] = Field(
        description="Rolling metric values keyed by metric name for this date.",
        json_schema_extra={
            "example": {
                "ROLLING_VOLATILITY": 0.1374,
                "ROLLING_SHARPE": 0.8123,
            }
        },
    )


class RollingMetricSeriesContext(BaseModel):
    requested: bool = Field(
        description="Whether rolling time-series points were requested for this window.",
        json_schema_extra={"example": True},
    )
    included: bool = Field(
        description="Whether rolling time-series points are included in the response for this window.",
        json_schema_extra={"example": True},
    )
    emitted_point_count: int = Field(
        default=0,
        description="Number of time-series points emitted for this window.",
        json_schema_extra={"example": 64},
    )
    reason: Literal["INCLUDED", "OMITTED_BY_REQUEST", "NO_METRIC_SERIES"] = Field(
        description="Deterministic reason for time-series inclusion behavior in this window.",
        json_schema_extra={"example": "INCLUDED"},
    )


class RollingWindowResult(BaseModel):
    window_length: int = Field(
        description="Rolling window length in observations.",
        json_schema_extra={"example": 63},
    )
    metric_summaries: dict[str, RollingMetricSummary] = Field(
        description="Rolling metric summaries keyed by metric name.",
        json_schema_extra={
            "example": {
                "ROLLING_VOLATILITY": {
                    "total_point_count": 64,
                    "computed_point_count": 44,
                    "coverage_ratio": 0.6875,
                    "min_observations_required": 21,
                    "warmup_point_count": 20,
                    "non_computed_point_count": 20,
                    "post_warmup_gap_point_count": 0,
                    "latest_observation_date": "2026-03-31",
                    "latest": 0.1374,
                    "average": 0.1221,
                    "minimum": 0.0913,
                    "maximum": 0.1662,
                    "p05": 0.0975,
                    "p50": 0.1218,
                    "p95": 0.1611,
                }
            }
        },
    )
    metric_series: list[RollingMetricSeriesPoint] | None = Field(
        default=None,
        description="Optional rolling metric time series for this window.",
        json_schema_extra={
            "example": [
                {
                    "date": "2026-02-28",
                    "metric_values": {
                        "ROLLING_VOLATILITY": 0.1374,
                        "ROLLING_SHARPE": 0.8123,
                    },
                }
            ]
        },
    )
    metric_series_context: RollingMetricSeriesContext = Field(
        description="Time-series inclusion context for this rolling window.",
        json_schema_extra={
            "example": {
                "requested": True,
                "included": True,
                "emitted_point_count": 64,
                "reason": "INCLUDED",
            }
        },
    )


class RollingBenchmarkContext(BaseModel):
    requested: bool = Field(
        description="Whether any benchmark-dependent rolling metrics were requested for this period.",
        json_schema_extra={"example": True},
    )
    available: bool = Field(
        description="Whether benchmark return observations were available in this period.",
        json_schema_extra={"example": True},
    )
    aligned: bool = Field(
        description="Whether benchmark return observations aligned with portfolio observations for requested rolling metrics.",
        json_schema_extra={"example": True},
    )
    reason: Literal[
        "NOT_REQUESTED", "BENCHMARK_UNAVAILABLE", "NO_ALIGNED_OBSERVATIONS", "APPLIED"
    ] = Field(
        description="Deterministic benchmark application outcome for the period.",
        json_schema_extra={"example": "APPLIED"},
    )


class RollingRiskFreeContext(BaseModel):
    requested: bool = Field(
        description="Whether rolling Sharpe was requested for this period.",
        json_schema_extra={"example": True},
    )
    available: bool = Field(
        description="Whether risk-free observations were available in this period.",
        json_schema_extra={"example": True},
    )
    aligned: bool = Field(
        description="Whether risk-free observations aligned with portfolio observations for rolling Sharpe.",
        json_schema_extra={"example": True},
    )
    reason: Literal[
        "NOT_REQUESTED", "RISK_FREE_UNAVAILABLE", "NO_ALIGNED_OBSERVATIONS", "APPLIED"
    ] = Field(
        description="Deterministic risk-free application outcome for the period.",
        json_schema_extra={"example": "APPLIED"},
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
