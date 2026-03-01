# lotus-risk Domain API Assessment

## Scope

This package documents the current `lotus-risk` API surface and evaluates it against:

- lotus-platform bounded context ownership
- platform operational endpoint expectations
- three execution modes for analytics APIs:
  - stateless
  - stateful
  - simulation

## Source-of-Truth Inputs Used

- `lotus-risk` runtime/router/contracts
- cross-repo consumers (`lotus-gateway`, `lotus-report`, `lotus-core`)
- lotus-platform governance references:
  - `rfcs/RFC-0065-lotus-performance-to-lotus-performance-and-lotus-risk-split.md`
  - `rfcs/RFC-0015-domain-boundaries-and-service-ownership.md`
  - `platform-contracts/cross-cutting-platform-contract.yaml`
  - `Scalability and Availability Standard.md`

## Endpoint Inventory

- Operational:
  - `GET /health`
  - `GET /health/live`
  - `GET /health/ready`
  - `GET /metadata`
  - `GET /ops`
  - `GET /metrics` (Prometheus exposure)
- Integration:
  - `GET /integration/capabilities`
- Domain analytics:
- `POST /analytics/risk/calculate`
- `POST /analytics/risk/drawdown`
- `POST /analytics/risk/concentration`
- `POST /analytics/risk/rolling-metrics`

## Current Dependency Summary

- Upstream dependencies (for live ecosystem usage):
  - Data sourcing expected from `lotus-core` integration contracts for stateful/simulation patterns.
  - Optional derived returns path through `lotus-performance` (already used by `lotus-report`) for risk-ready daily return series.
- Downstream consumers:
  - `lotus-gateway`
  - `lotus-report`
  - `lotus-core` (indirect via 410 redirects that point callers to lotus-risk)

## Findings Snapshot

- `lotus-risk` is correctly the bounded-context owner for risk/concentration analytics.
- Concentration API supports stateless, stateful, and simulation modes.
- Legacy concentration payload aliases are removed; canonical envelope is required.
- `/ops` endpoint is implemented with typed diagnostics contract.
- Legacy endpoint `/analytics/workbench/risk-proxy` is removed from runtime surface.

See per-endpoint detail:

- `docs/domain-apis/endpoint-matrix.md`
- `docs/domain-apis/operational-endpoints.md`
- `docs/domain-apis/integration-capabilities.md`
- `docs/domain-apis/risk-calculate.md`
- `docs/domain-apis/risk-drawdown.md`
- `docs/domain-apis/risk-concentration.md`
- `docs/domain-apis/risk-rolling-metrics.md`
- `docs/domain-apis/lotus-core-requirements-for-issuer-concentration.md`
