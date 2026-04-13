from __future__ import annotations

from time import perf_counter

from prometheus_client import Counter, Histogram


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


def observation_start() -> float:
    return perf_counter()


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
