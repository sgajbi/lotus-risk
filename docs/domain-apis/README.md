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
- `POST /analytics/risk/historical-attribution` (stateless plus approved stateful scope implemented; stateful `ACTIVE_RISK + ISSUER` remains intentionally gated)

## Current Dependency Summary

- Upstream dependencies (for live ecosystem usage):
  - `lotus-core` provides portfolio snapshots, simulation sessions, instrument enrichment,
    position analytics history, issuer/instrument authority, and risk-free reference series.
  - `lotus-performance` provides portfolio returns, benchmark returns, and supported
    benchmark exposure context for performance-aligned risk attribution.
  - Upstream failures are mapped to deterministic Lotus error codes and structured categories.
- Downstream consumers:
  - `lotus-gateway`
  - `lotus-report`
  - `lotus-core` (indirect via 410 redirects that point callers to lotus-risk)

## Findings Snapshot

- `lotus-risk` is correctly the bounded-context owner for risk/concentration analytics.
- Concentration API supports stateless, stateful, and simulation modes.
- Legacy concentration payload aliases are removed; canonical envelope is required.
- `/ops` endpoint is implemented with typed diagnostics contract.
- The current service-wide readiness view is maintained in the endpoint matrix and reflects the
  current gold-standard status by endpoint and mode.
- Live validation breadth is governed by `docs/operations/live-risk-validation-matrix.md`. The
  default live baseline is canonical portfolio `PB_SG_GLOBAL_BAL_001`; additional enterprise
  archetypes require real seeded portfolio IDs and endpoint evidence before they can be counted as
  validated.

See per-endpoint detail:

- `docs/domain-apis/endpoint-matrix.md`
- `docs/domain-apis/operational-endpoints.md`
- `docs/domain-apis/integration-capabilities.md`
- `docs/domain-apis/risk-calculate.md`
- `docs/domain-apis/risk-drawdown.md`
- `docs/domain-apis/risk-concentration.md`
- `docs/domain-apis/risk-rolling-metrics.md`
- `docs/domain-apis/risk-historical-attribution.md`
- `docs/domain-apis/risk-upstream-failure-behavior.md`
- `docs/domain-apis/risk-audit-lineage.md`
- `docs/domain-apis/risk-observability.md`
- `docs/domain-apis/risk-product-surface-alignment.md`
- `docs/domain-apis/lotus-core-requirements-for-issuer-concentration.md`
- `docs/domain-apis/RFC-0082-upstream-contract-family-map.md`
