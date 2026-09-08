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
from app.services.observability_ports import (
    record_analytics_freshness_bucket,
    record_calculation_supportability,
)
from app.services.supportability_periods import (
    assess_period_results,
    period_results_supportability_state,
    select_supportability_reason,
    supportability_reason_for_error,
)


@dataclass(frozen=True)
class _RiskMetricSupportabilityScan:
    degraded_reasons: list[RiskSupportabilityReason]
    empty_period_count: int
    degraded_metric_count: int


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

    return period_results_supportability_state(
        freshness_bucket=freshness_bucket,
        assessment=assess_period_results(results),
        evaluated_period_count=len(results),
    )


def supportability_from_attribution_results(
    *,
    returns: Sequence[ReturnPoint],
    as_of_date: dt.date,
    results: Mapping[str, Any],
) -> RiskCalculationSupportability:
    """Supportability for a historical-attribution response.

    The structural group-return limitation is **composed with** the period
    assessment, not substituted for it. It was substituted (#293, introduced by
    #287), which discarded every actionable reason and every count: a period
    failing with `Insufficient data` reported `group_return_series_unavailable`
    and `degraded_metric_count=0` -- naming a limitation the operator cannot act
    on while hiding the failure they can, and reporting zero degraded results at
    the exact moment one had failed.
    """
    baseline = supportability_from_period_results(
        returns=returns,
        as_of_date=as_of_date,
        results=results,
    )

    # No observations means nothing was decomposed, so there is no weight proxy
    # to qualify and the baseline already names why. Every other response
    # composes.
    #
    # This guard is deliberately on the returns and not on the attribution sets.
    # A set-count gate looks more precise and is worse on both counts: the
    # engine short-circuits an empty response before this function is called
    # (`attribution_engine.calculate_historical_attribution`), so the set-count
    # branch was unreachable from the endpoint -- and where it did fire it fell
    # through to a baseline that can be `ready`, which is the single answer this
    # response must never give. Proved by mutation: replacing the set gate with
    # `if False` changed no test, because no test could reach it.
    if not returns:
        return baseline

    assessment = assess_period_results(results)

    # The limitation enters as one more degradation reason and takes its rank in
    # the existing precedence: below the actionable failures, above staleness and
    # self-flagged quality. So a response that decomposed *and* failed somewhere
    # reports the failure -- the reason an operator can act on -- while a
    # response that only decomposed reports the limitation. No new rule; the
    # precedence tuple already placed this reason for exactly this purpose.
    #
    # `degraded` unconditionally, never `ready`: the proxy is present whenever a
    # set is, and a clean-looking decomposition is precisely the one a consumer
    # would present as empirical risk attribution.
    #
    # Counts stay the period assessment's. `degraded_metric_count` is defined by
    # the contract as results carrying deterministic error details; an
    # attribution set carries a structural limitation, not an error. Counting
    # sets there overstated the field on clean responses and -- because a failed
    # period returns no sets -- reported 0 on exactly the responses that failed.
    return RiskCalculationSupportability(
        state="degraded",
        reason=select_supportability_reason(
            [*assessment.degraded_reasons, "group_return_series_unavailable"]
        ),
        freshness_bucket=baseline.freshness_bucket,
        degraded_metric_count=assessment.degraded_result_count,
        empty_period_count=assessment.empty_period_count,
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

    scan = _scan_risk_metric_supportability(results)
    if scan.degraded_metric_count:
        freshness_bucket = freshness_bucket_from_returns(returns, as_of_date=as_of_date)
        return RiskCalculationSupportability(
            state="degraded",
            reason=select_supportability_reason(scan.degraded_reasons),
            freshness_bucket=freshness_bucket,
            degraded_metric_count=scan.degraded_metric_count,
            empty_period_count=scan.empty_period_count,
            evaluated_period_count=len(results),
        )
    return supportability


def _scan_risk_metric_supportability(
    results: Mapping[str, Any],
) -> _RiskMetricSupportabilityScan:
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
                degraded_reasons.append(supportability_reason_for_error(error))

    return _RiskMetricSupportabilityScan(
        degraded_reasons=degraded_reasons,
        empty_period_count=empty_period_count,
        degraded_metric_count=degraded_metric_count,
    )


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
        freshness_bucket="current",
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
