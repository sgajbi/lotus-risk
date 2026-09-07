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


#: Which reason wins when a period degrades for several at once, most severe
#: first. The ordering is real domain content -- a missing benchmark outranks a
#: failure to align observations -- so it cannot be derived from the alias.
#:
#: It must, however, be **total** over the alias. It was not: four of ten members
#: were ranked and the other six exhausted a `next()` with no default, so every
#: value the signature declares as acceptable except four raised a bare
#: `StopIteration`. Safe only by coincidence of who called it (#281).
#:
#: The original four keep their exact relative order. The rest are placed by
#: severity, and the placements are judgements rather than observations, because
#: these reasons cannot currently co-occur with the original four -- that is
#: precisely why the gap went unnoticed. Stated plainly so a later reader can
#: disagree with a specific decision instead of an unexplained tuple:
#:
#:   permission_blocked            nothing may be computed or shown at all
#:   unsupported_input_mode        the request cannot be served in this shape
#:   no_return_observations        no input data whatsoever, not merely too little
#:   benchmark_unavailable         a required input is absent          [original]
#:   insufficient_aligned_observations  present but not comparable     [original]
#:   insufficient_observations     present, comparable, too few        [original]
#:   group_return_series_unavailable  a structural source limitation, not a shortfall
#:   stale_source_observations     sufficient data, but old
#:   calculation_quality_issue     the calculation ran and flagged itself  [original]
_SUPPORTABILITY_REASON_PRECEDENCE: tuple[RiskSupportabilityReason, ...] = (
    "permission_blocked",
    "unsupported_input_mode",
    "no_return_observations",
    "benchmark_unavailable",
    "insufficient_aligned_observations",
    "insufficient_observations",
    "group_return_series_unavailable",
    "stale_source_observations",
    "calculation_quality_issue",
)

#: Members that are deliberately unranked, each with the reason.
#:
#: `calculation_complete` is the reason carried by a *ready* response. It is not
#: a degradation and can never be selected among degradations, so ranking it
#: would invent an ordering for a case that cannot arise.
_NOT_A_DEGRADATION_REASON: frozenset[RiskSupportabilityReason] = frozenset({"calculation_complete"})


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
    """The most severe reason present, by the precedence above.

    Raises `ValueError` naming the input when no reason is ranked. The previous
    `next()` had no default, so an unranked reason raised a bare
    `StopIteration` carrying neither the value nor this module -- and inside a
    generator or `async` frame PEP 479 rewrites that into
    `RuntimeError: generator raised StopIteration`, which points at neither.

    The precedence is total over the alias and a test holds it that way, so
    reaching this raise means a reason was added to `RiskSupportabilityReason`
    without a rank, or an empty sequence arrived.
    """
    available_reasons = set(reasons)
    for reason in _SUPPORTABILITY_REASON_PRECEDENCE:
        if reason in available_reasons:
            return reason
    raise ValueError(
        "select_supportability_reason has no precedence for "
        f"{sorted(available_reasons)!r}; ranked reasons are "
        f"{list(_SUPPORTABILITY_REASON_PRECEDENCE)!r}"
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
