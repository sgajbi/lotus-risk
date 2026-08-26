from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager

from app.observability import (
    observation_start as _observation_start,
)
from app.observability import (
    observe_risk_metric_duration as _observe_risk_metric_duration,
)
from app.observability import (
    record_analytics_freshness_bucket as _record_analytics_freshness_bucket,
)
from app.observability import (
    record_calculation_supportability as _record_calculation_supportability,
)
from app.observability import (
    record_endpoint_execution as _record_endpoint_execution,
)
from app.observability import (
    record_risk_metric_requests as _record_risk_metric_requests,
)


def record_risk_metric_requests(metrics: Sequence[str]) -> None:
    _record_risk_metric_requests(metrics)


def observe_risk_metric_duration(metric_name: str) -> AbstractContextManager[None]:
    return _observe_risk_metric_duration(metric_name)


def observation_start() -> float:
    return _observation_start()


def record_endpoint_execution(
    *,
    endpoint: str,
    input_mode: str,
    outcome: str,
    started_at: float,
) -> None:
    _record_endpoint_execution(
        endpoint=endpoint,
        input_mode=input_mode,
        outcome=outcome,
        started_at=started_at,
    )


def record_calculation_supportability(
    *,
    operation: str,
    supportability_state: str,
    reason: str,
    freshness_bucket: str,
) -> None:
    _record_calculation_supportability(
        operation=operation,
        supportability_state=supportability_state,
        reason=reason,
        freshness_bucket=freshness_bucket,
    )


def record_analytics_freshness_bucket(
    *,
    operation: str,
    freshness_bucket: str,
    supportability_state: str,
) -> None:
    _record_analytics_freshness_bucket(
        operation=operation,
        freshness_bucket=freshness_bucket,
        supportability_state=supportability_state,
    )
