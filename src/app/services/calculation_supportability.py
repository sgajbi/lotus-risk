from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.contracts.risk import (
    ReturnPoint,
    RiskCalculationSupportability,
    RiskFreshnessBucket,
    RiskSupportabilityReason,
)
from app.observability import record_analytics_freshness_bucket, record_calculation_supportability


@dataclass(frozen=True)
class _PeriodSupportabilityAssessment:
    degraded_reasons: list[RiskSupportabilityReason]
    empty_period_count: int
    degraded_result_count: int


_SUPPORTABILITY_REASON_PRECEDENCE: tuple[RiskSupportabilityReason, ...] = (
    "benchmark_unavailable",
    "insufficient_aligned_observations",
    "insufficient_observations",
    "calculation_quality_issue",
)


def default_calculation_supportability() -> RiskCalculationSupportability:
    return RiskCalculationSupportability(
        state="ready",
        reason="calculation_complete",
        freshness_bucket="unknown",
    )


def freshness_bucket_from_returns(
    returns: Sequence[ReturnPoint],
    *,
    as_of_date: dt.date,
) -> RiskFreshnessBucket:
    if not returns:
        return "unknown"
    latest_observation_date = max(point.date for point in returns)
    age_days = (as_of_date - latest_observation_date).days
    if age_days <= 0:
        return "current"
    if age_days <= 1:
        return "same_day"
    return "stale"


def _supportability_reason_for_error(error: str) -> RiskSupportabilityReason:
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


def _select_reason(reasons: Sequence[RiskSupportabilityReason]) -> RiskSupportabilityReason:
    available_reasons = set(reasons)
    return next(
        reason for reason in _SUPPORTABILITY_REASON_PRECEDENCE if reason in available_reasons
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
            return _supportability_reason_for_error(str(reason))
        if aligned is False:
            return "insufficient_aligned_observations"
    return None


def _assess_period_results(
    results: Mapping[str, Any],
) -> _PeriodSupportabilityAssessment:
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
            degraded_reasons.append(_supportability_reason_for_error(error))
            continue
        dependency_reason = _dependency_degradation_reason(period_result)
        if dependency_reason is not None:
            degraded_result_count += 1
            degraded_reasons.append(dependency_reason)

    return _PeriodSupportabilityAssessment(
        degraded_reasons=degraded_reasons,
        empty_period_count=empty_period_count,
        degraded_result_count=degraded_result_count,
    )


def _period_results_supportability_state(
    *,
    freshness_bucket: RiskFreshnessBucket,
    assessment: _PeriodSupportabilityAssessment,
    evaluated_period_count: int,
) -> RiskCalculationSupportability:
    if assessment.degraded_result_count:
        return RiskCalculationSupportability(
            state="degraded",
            reason=_select_reason(assessment.degraded_reasons),
            freshness_bucket=freshness_bucket,
            degraded_metric_count=assessment.degraded_result_count,
            empty_period_count=assessment.empty_period_count,
            evaluated_period_count=evaluated_period_count,
        )

    if assessment.empty_period_count:
        return RiskCalculationSupportability(
            state="empty",
            reason="insufficient_observations",
            freshness_bucket=freshness_bucket,
            empty_period_count=assessment.empty_period_count,
            evaluated_period_count=evaluated_period_count,
        )

    if freshness_bucket == "stale":
        return RiskCalculationSupportability(
            state="stale",
            reason="stale_source_observations",
            freshness_bucket=freshness_bucket,
            evaluated_period_count=evaluated_period_count,
        )

    return RiskCalculationSupportability(
        state="ready",
        reason="calculation_complete",
        freshness_bucket=freshness_bucket,
        evaluated_period_count=evaluated_period_count,
    )


def supportability_from_period_results(
    *,
    returns: Sequence[ReturnPoint],
    as_of_date: dt.date,
    results: Mapping[str, Any],
) -> RiskCalculationSupportability:
    freshness_bucket = freshness_bucket_from_returns(returns, as_of_date=as_of_date)
    if not returns:
        return RiskCalculationSupportability(
            state="empty",
            reason="no_return_observations",
            freshness_bucket=freshness_bucket,
            evaluated_period_count=len(results),
        )

    return _period_results_supportability_state(
        freshness_bucket=freshness_bucket,
        assessment=_assess_period_results(results),
        evaluated_period_count=len(results),
    )


def supportability_from_attribution_results(
    *,
    returns: Sequence[ReturnPoint],
    as_of_date: dt.date,
    results: Mapping[str, Any],
) -> RiskCalculationSupportability:
    supportability = supportability_from_period_results(
        returns=returns,
        as_of_date=as_of_date,
        results=results,
    )
    if supportability.state == "empty":
        return supportability

    degraded_set_count = 0
    for period_result in results.values():
        attribution_sets = getattr(period_result, "attribution_sets", ())
        if not isinstance(attribution_sets, Sequence):
            continue
        for attribution_set in attribution_sets:
            quality_flags = getattr(attribution_set, "quality_flags", ())
            if isinstance(quality_flags, Sequence) and quality_flags:
                degraded_set_count += 1

    if degraded_set_count == 0:
        return supportability

    freshness_bucket = freshness_bucket_from_returns(returns, as_of_date=as_of_date)
    return RiskCalculationSupportability(
        state="degraded",
        reason="calculation_quality_issue",
        freshness_bucket=freshness_bucket,
        degraded_metric_count=degraded_set_count,
        empty_period_count=supportability.empty_period_count,
        evaluated_period_count=len(results),
    )


def supportability_from_risk_metric_results(
    *,
    returns: Sequence[ReturnPoint],
    as_of_date: dt.date,
    results: Mapping[str, Any],
) -> RiskCalculationSupportability:
    supportability = supportability_from_period_results(
        returns=returns,
        as_of_date=as_of_date,
        results=results,
    )
    if supportability.state == "empty":
        return supportability

    degraded_reasons: list[RiskSupportabilityReason] = []
    empty_period_count = 0
    degraded_metric_count = 0
    for period_result in results.values():
        if getattr(period_result, "portfolio_observation_count", None) == 0:
            empty_period_count += 1
        metrics = getattr(period_result, "metrics", {})
        if not isinstance(metrics, Mapping):
            continue
        for metric_result in metrics.values():
            details = getattr(metric_result, "details", None)
            if not isinstance(details, Mapping):
                continue
            error = details.get("error")
            if isinstance(error, str):
                degraded_metric_count += 1
                degraded_reasons.append(_supportability_reason_for_error(error))

    if degraded_metric_count:
        freshness_bucket = freshness_bucket_from_returns(returns, as_of_date=as_of_date)
        return RiskCalculationSupportability(
            state="degraded",
            reason=_select_reason(degraded_reasons),
            freshness_bucket=freshness_bucket,
            degraded_metric_count=degraded_metric_count,
            empty_period_count=empty_period_count,
            evaluated_period_count=len(results),
        )
    return supportability


def supportability_from_concentration_response(
    *,
    covered_position_count_current: int,
    covered_position_count_proposed: int,
    total_position_count_current: int,
    total_position_count_proposed: int,
    issuer_note: str | None,
) -> RiskCalculationSupportability:
    total_positions = total_position_count_current + total_position_count_proposed
    covered_positions = covered_position_count_current + covered_position_count_proposed
    if total_positions == 0:
        return RiskCalculationSupportability(
            state="empty",
            reason="insufficient_observations",
            freshness_bucket="unknown",
            empty_period_count=1,
            evaluated_period_count=1,
        )
    if covered_positions == 0 or issuer_note:
        return RiskCalculationSupportability(
            state="degraded",
            reason="calculation_quality_issue",
            freshness_bucket="unknown",
            degraded_metric_count=1,
            evaluated_period_count=1,
        )
    return RiskCalculationSupportability(
        state="ready",
        reason="calculation_complete",
        freshness_bucket="unknown",
        evaluated_period_count=1,
    )


def record_operation_supportability(
    *,
    operation: str,
    supportability: RiskCalculationSupportability,
) -> None:
    record_calculation_supportability(
        operation=operation,
        supportability_state=supportability.state,
        reason=supportability.reason,
        freshness_bucket=supportability.freshness_bucket,
    )
    record_analytics_freshness_bucket(
        operation=operation,
        freshness_bucket=supportability.freshness_bucket,
        supportability_state=supportability.state,
    )
