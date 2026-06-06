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
