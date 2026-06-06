from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast

from app.contracts.rolling import (
    ROLLING_BENCHMARK_METRICS,
    RollingBenchmarkContext,
    RollingRiskFreeContext,
)
from app.services.rolling_metric_series import ROLLING_SHARPE_METRIC

RollingDependencyReason = Literal[
    "NOT_REQUESTED",
    "BENCHMARK_UNAVAILABLE",
    "RISK_FREE_UNAVAILABLE",
    "NO_ALIGNED_OBSERVATIONS",
    "APPLIED",
]
RollingBenchmarkReason = Literal[
    "NOT_REQUESTED",
    "BENCHMARK_UNAVAILABLE",
    "NO_ALIGNED_OBSERVATIONS",
    "APPLIED",
]
RollingRiskFreeReason = Literal[
    "NOT_REQUESTED",
    "RISK_FREE_UNAVAILABLE",
    "NO_ALIGNED_OBSERVATIONS",
    "APPLIED",
]


@dataclass(frozen=True)
class _RollingDependencyDecision:
    requested: bool
    available: bool
    aligned: bool
    reason: RollingDependencyReason


def _dependency_decision(
    *,
    requested: bool,
    source_series_count: int,
    aligned_series_count: int,
    unavailable_reason: RollingDependencyReason,
) -> _RollingDependencyDecision:
    if not requested:
        return _RollingDependencyDecision(
            requested=False,
            available=False,
            aligned=False,
            reason="NOT_REQUESTED",
        )
    if source_series_count == 0:
        return _RollingDependencyDecision(
            requested=True,
            available=False,
            aligned=False,
            reason=unavailable_reason,
        )
    if aligned_series_count == 0:
        return _RollingDependencyDecision(
            requested=True,
            available=True,
            aligned=False,
            reason="NO_ALIGNED_OBSERVATIONS",
        )
    return _RollingDependencyDecision(
        requested=True,
        available=True,
        aligned=True,
        reason="APPLIED",
    )


def benchmark_context(
    requested_metrics: Sequence[str],
    *,
    benchmark_series_count: int,
    aligned_benchmark_series_count: int,
) -> RollingBenchmarkContext:
    decision = _dependency_decision(
        requested=any(metric in ROLLING_BENCHMARK_METRICS for metric in requested_metrics),
        source_series_count=benchmark_series_count,
        aligned_series_count=aligned_benchmark_series_count,
        unavailable_reason="BENCHMARK_UNAVAILABLE",
    )
    return RollingBenchmarkContext(
        requested=decision.requested,
        available=decision.available,
        aligned=decision.aligned,
        reason=cast(RollingBenchmarkReason, decision.reason),
    )


def risk_free_context(
    requested_metrics: Sequence[str],
    *,
    risk_free_series_count: int,
    aligned_risk_free_series_count: int,
) -> RollingRiskFreeContext:
    decision = _dependency_decision(
        requested=ROLLING_SHARPE_METRIC in requested_metrics,
        source_series_count=risk_free_series_count,
        aligned_series_count=aligned_risk_free_series_count,
        unavailable_reason="RISK_FREE_UNAVAILABLE",
    )
    return RollingRiskFreeContext(
        requested=decision.requested,
        available=decision.available,
        aligned=decision.aligned,
        reason=cast(RollingRiskFreeReason, decision.reason),
    )
