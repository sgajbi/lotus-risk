# Lotus Risk Observability

`lotus-risk` exposes correlation-aware request telemetry, endpoint execution metrics, calculation
supportability metrics, analytics freshness buckets, readiness state, and Prometheus metrics.

## Required Signals

1. Correlation identifiers must be accepted, generated when absent, returned to callers, and
   propagated to downstream services.
2. Metrics labels must stay bounded and must never expose portfolio identifiers, client
   identifiers, trace identifiers, correlation identifiers, request bodies, or response bodies.
3. Readiness must distinguish ready, degraded, and draining dependency posture.
4. Downstream failures must preserve source service, operation, retryability, and mapped platform
   error category.

## Refactor Guardrail

Router extraction must preserve existing RFC-0108 supportability metrics and the corresponding
unit tests.

## Dashboard And Alert Evidence

The governed monitoring contract lives at
`contracts/observability/lotus-risk-monitoring.v1.json`. It defines:

1. bounded Prometheus metric labels,
2. the operator dashboard panels for endpoint, upstream, supportability, and HTTP status posture,
3. alert definitions for endpoint failures, upstream dependency failures, degraded calculation
   supportability, and HTTP 5xx responses,
4. runbook anchors in `docs/runbooks/service-operations.md`.

`make observability-contract-validate` verifies that declared metrics match the implementation,
that dashboards and alerts reference implemented metrics, and that alert runbook anchors exist.
