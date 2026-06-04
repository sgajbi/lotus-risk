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
