from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.contracts.risk import (
    RiskCalculationSupportability,
    RiskFreshnessBucket,
    RiskSupportabilityReason,
    RiskSupportabilityState,
)


@dataclass(frozen=True)
class PeriodSupportabilityAssessment:
    degraded_reasons: list[RiskSupportabilityReason]
    empty_period_count: int
    degraded_result_count: int


@dataclass(frozen=True)
class _PeriodSupportabilityOutcome:
    state: RiskSupportabilityState
    reason: RiskSupportabilityReason
    degraded_metric_count: int = 0
    empty_period_count: int = 0


_SUPPORTABILITY_REASON_PRECEDENCE: tuple[RiskSupportabilityReason, ...] = (
    "benchmark_unavailable",
    "insufficient_aligned_observations",
    "insufficient_observations",
    "calculation_quality_issue",
)


def supportability_reason_for_error(error: str) -> RiskSupportabilityReason:
    if error in {
        "Benchmark returns required for benchmark-dependent metric",
        "BENCHMARK_UNAVAILABLE",
    }:
        return "benchmark_unavailable"
    if error in {"Insufficient aligned observations", "NO_ALIGNED_OBSERVATIONS"}:
        return "insufficient_aligned_observations"
    if error == "Insufficient data":
        return "insufficient_observations"
    return "calculation_quality_issue"


def select_supportability_reason(
    reasons: Sequence[RiskSupportabilityReason],
) -> RiskSupportabilityReason:
    available_reasons = set(reasons)
    return next(
        reason for reason in _SUPPORTABILITY_REASON_PRECEDENCE if reason in available_reasons
    )


def assess_period_results(
    results: Mapping[str, Any],
) -> PeriodSupportabilityAssessment:
    degraded_reasons: list[RiskSupportabilityReason] = []
    empty_period_count = 0
    degraded_result_count = 0

    for period_result in results.values():
        observation_count = _observation_count(period_result)
        if observation_count == 0:
            empty_period_count += 1

        error = getattr(period_result, "error", None)
        if isinstance(error, str):
            degraded_result_count += 1
            degraded_reasons.append(supportability_reason_for_error(error))
            continue
        dependency_reason = _dependency_degradation_reason(period_result)
        if dependency_reason is not None:
            degraded_result_count += 1
            degraded_reasons.append(dependency_reason)

    return PeriodSupportabilityAssessment(
        degraded_reasons=degraded_reasons,
        empty_period_count=empty_period_count,
        degraded_result_count=degraded_result_count,
    )


def period_results_supportability_state(
    *,
    freshness_bucket: RiskFreshnessBucket,
    assessment: PeriodSupportabilityAssessment,
    evaluated_period_count: int,
) -> RiskCalculationSupportability:
    outcome = _period_supportability_outcome(
        freshness_bucket=freshness_bucket,
        assessment=assessment,
    )
    return _risk_calculation_supportability(
        outcome=outcome,
        freshness_bucket=freshness_bucket,
        evaluated_period_count=evaluated_period_count,
    )


def _period_supportability_outcome(
    *,
    freshness_bucket: RiskFreshnessBucket,
    assessment: PeriodSupportabilityAssessment,
) -> _PeriodSupportabilityOutcome:
    if assessment.degraded_result_count:
        return _PeriodSupportabilityOutcome(
            state="degraded",
            reason=select_supportability_reason(assessment.degraded_reasons),
            degraded_metric_count=assessment.degraded_result_count,
            empty_period_count=assessment.empty_period_count,
        )

    if assessment.empty_period_count:
        return _PeriodSupportabilityOutcome(
            state="empty",
            reason="insufficient_observations",
            empty_period_count=assessment.empty_period_count,
        )

    if freshness_bucket == "stale":
        return _PeriodSupportabilityOutcome(
            state="stale",
            reason="stale_source_observations",
        )

    return _PeriodSupportabilityOutcome(state="ready", reason="calculation_complete")


def _risk_calculation_supportability(
    *,
    outcome: _PeriodSupportabilityOutcome,
    freshness_bucket: RiskFreshnessBucket,
    evaluated_period_count: int,
) -> RiskCalculationSupportability:
    return RiskCalculationSupportability(
        state=outcome.state,
        reason=outcome.reason,
        freshness_bucket=freshness_bucket,
        degraded_metric_count=outcome.degraded_metric_count,
        empty_period_count=outcome.empty_period_count,
        evaluated_period_count=evaluated_period_count,
    )


def _observation_count(period_result: Any) -> int | None:
    for attribute_name in ("portfolio_observation_count", "series_count"):
        value = getattr(period_result, attribute_name, None)
        if isinstance(value, int):
            return value
    return None


def _dependency_degradation_reason(period_result: Any) -> RiskSupportabilityReason | None:
    for attribute_name in (
        "relative_to_benchmark_context",
        "benchmark_context",
        "risk_free_context",
    ):
        context = getattr(period_result, attribute_name, None)
        if context is None or getattr(context, "requested", False) is not True:
            continue
        reason = getattr(context, "reason", None)
        applied = getattr(context, "applied", None)
        available = getattr(context, "available", None)
        aligned = getattr(context, "aligned", None)
        if applied is False or available is False:
            return supportability_reason_for_error(str(reason))
        if aligned is False:
            return "insufficient_aligned_observations"
    return None
