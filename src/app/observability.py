from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from time import perf_counter

from prometheus_client import Counter, Histogram

from app.observability_contracts import (
    RISK_ANALYTICS_FRESHNESS_METRIC_LABELS,
    RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS,
)

ENDPOINT_EXECUTIONS_TOTAL = Counter(
    "lotus_risk_endpoint_executions_total",
    "Risk analytics endpoint executions by endpoint, input mode, and outcome.",
    ["endpoint", "input_mode", "outcome"],
)
ENDPOINT_EXECUTION_SECONDS = Histogram(
    "lotus_risk_endpoint_execution_seconds",
    "Risk analytics endpoint execution duration by endpoint, input mode, and outcome.",
    ["endpoint", "input_mode", "outcome"],
)
UPSTREAM_REQUESTS_TOTAL = Counter(
    "lotus_risk_upstream_requests_total",
    "Upstream dependency requests by dependency, operation, outcome, and failure category.",
    ["dependency", "operation", "outcome", "category"],
)
UPSTREAM_REQUEST_SECONDS = Histogram(
    "lotus_risk_upstream_request_seconds",
    "Upstream dependency request duration by dependency, operation, outcome, and failure category.",
    ["dependency", "operation", "outcome", "category"],
)
CALCULATION_SUPPORTABILITY_TOTAL = Counter(
    "lotus_risk_calculation_supportability_total",
    "Risk calculation supportability posture by bounded operation, state, reason, and freshness bucket.",
    RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS,
)
ANALYTICS_FRESHNESS_BUCKET_TOTAL = Counter(
    "lotus_analytics_freshness_bucket_total",
    "Backend analytics freshness and supportability posture by service, operation, and bounded freshness bucket.",
    RISK_ANALYTICS_FRESHNESS_METRIC_LABELS,
)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "HTTP requests by route handler, method, and status class.",
    ["handler", "method", "status"],
)
RISK_METRIC_REQUESTED_TOTAL = Counter(
    "risk_metric_requested_total",
    "Number of risk metric requests by metric name.",
    ["metric_name"],
)
RISK_METRIC_DURATION_SECONDS = Histogram(
    "risk_metric_duration_seconds",
    "Risk metric calculation duration by metric name.",
    ["metric_name"],
)


def observation_start() -> float:
    return perf_counter()


def record_risk_metric_requests(metrics: Sequence[str]) -> None:
    for metric in metrics:
        RISK_METRIC_REQUESTED_TOTAL.labels(metric_name=metric).inc()


def observe_risk_metric_duration(metric_name: str) -> AbstractContextManager[None]:
    return RISK_METRIC_DURATION_SECONDS.labels(metric_name=metric_name).time()


def record_endpoint_execution(
    *,
    endpoint: str,
    input_mode: str,
    outcome: str,
    started_at: float,
) -> None:
    elapsed = max(perf_counter() - started_at, 0.0)
    ENDPOINT_EXECUTIONS_TOTAL.labels(
        endpoint=endpoint,
        input_mode=input_mode,
        outcome=outcome,
    ).inc()
    ENDPOINT_EXECUTION_SECONDS.labels(
        endpoint=endpoint,
        input_mode=input_mode,
        outcome=outcome,
    ).observe(elapsed)


def record_upstream_request(
    *,
    dependency: str,
    operation: str,
    outcome: str,
    category: str,
    started_at: float,
) -> None:
    elapsed = max(perf_counter() - started_at, 0.0)
    UPSTREAM_REQUESTS_TOTAL.labels(
        dependency=dependency,
        operation=operation,
        outcome=outcome,
        category=category,
    ).inc()
    UPSTREAM_REQUEST_SECONDS.labels(
        dependency=dependency,
        operation=operation,
        outcome=outcome,
        category=category,
    ).observe(elapsed)


def record_calculation_supportability(
    *,
    operation: str,
    supportability_state: str,
    reason: str,
    freshness_bucket: str,
) -> None:
    CALCULATION_SUPPORTABILITY_TOTAL.labels(
        operation=operation,
        supportability_state=supportability_state,
        reason=reason,
        freshness_bucket=freshness_bucket,
    ).inc()


def record_analytics_freshness_bucket(
    *,
    operation: str,
    freshness_bucket: str,
    supportability_state: str,
) -> None:
    ANALYTICS_FRESHNESS_BUCKET_TOTAL.labels(
        service="lotus-risk",
        operation=operation,
        freshness_bucket=freshness_bucket,
        supportability_state=supportability_state,
    ).inc()


def record_http_request(*, handler: str, method: str, status_code: int) -> None:
    status_class = f"{status_code // 100}xx"
    HTTP_REQUESTS_TOTAL.labels(handler=handler, method=method.upper(), status=status_class).inc()
