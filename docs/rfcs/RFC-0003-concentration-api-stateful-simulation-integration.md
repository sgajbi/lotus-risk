# RFC-0003 - Concentration API Stateful and Simulation Integration via lotus-core Snapshot

- Status: Implemented (v1 scope), Partially complete for full RFC scope
- Date: 2026-02-27
- Owners: lotus-risk
- Upstream dependency owners: lotus-core
- Related: lotus-core RFC 058, lotus-platform RFC-0067

## Summary

Evolve `POST /analytics/risk/concentration` to support all three execution modes with one canonical contract:

1. `stateless` (caller supplies full positions)
2. `stateful` (lotus-risk resolves positions from lotus-core by identifiers)
3. `simulation` (lotus-risk resolves baseline/projected from lotus-core simulation snapshot)

The endpoint remains domain-owned by `lotus-risk`; `lotus-core` remains data/snapshot provider.

Hard boundary:

1. Callers do not call lotus-core directly for concentration workflows.
2. lotus-risk orchestrates all required lotus-core simulation and snapshot calls.
3. lotus-risk does not build or mutate portfolio state locally; it only calculates analytics from lotus-core-provided baseline and projected states.

## Problem

Today concentration is stateless-only in lotus-risk. That blocks ecosystem-native workflows where consumers pass identifiers (`portfolioId`, `asOfDate`, `sessionId`) and expect lotus-risk to source canonical data from lotus-core.

## Goals

1. Keep a single concentration endpoint in lotus-risk with explicit mode semantics.
2. Use lotus-core generic snapshot endpoint (`/integration/portfolios/{portfolio_id}/core-snapshot`) as the primary upstream contract.
3. Support current HHI output and extend to additional concentration types: single-position and issuer concentration (with optional sector/country rollout).
4. Preserve RFC-0067 vocabulary and OpenAPI quality gates.

## Non-Goals

1. Create concentration-specific endpoints in lotus-core.
2. Move concentration analytics ownership out of lotus-risk.
3. Build presentation/reporting responses in lotus-risk.

## Upstream and Downstream Boundaries

### Upstream (allowed)

1. `lotus-core` (required): positions, valuation context, simulation snapshots.
2. `lotus-performance` (optional/future): not required for concentration v1 integration.

### Downstream (expected)

1. `lotus-report`
2. `lotus-gateway`
3. `lotus-advise` and `lotus-manage` for simulation workflows

No additional runtime dependencies should be introduced for this RFC scope.

## Decision

Keep `POST /analytics/risk/concentration` as the only concentration API and add a mode envelope:

```json
{
  "inputMode": "stateful | simulation | stateless",
  "statefulInput": {},
  "simulationInput": {},
  "statelessInput": {}
}
```

No legacy payload aliases are supported. Only canonical mode envelope payloads are accepted.

## Mode Contracts

### 1) Stateless

Caller provides all positions directly.

Required:

1. `statelessInput.currentPositions[]` with `securityId`, `quantity`, optional `marketValueBase`, `weight`.
2. `statelessInput.projectedPositions[]` with `securityId`, `proposedQuantity`, optional `projectedMarketValueBase`, `projectedWeight`.

### 2) Stateful

Caller provides only identifiers; lotus-risk sources data from lotus-core snapshot in `BASELINE` mode.

Required:

1. `statefulInput.portfolioId`
2. `statefulInput.asOfDate`

Optional:

1. `statefulInput.reportingCurrency` (defaults to portfolio currency if omitted)
2. `statefulInput.includeCashPositions` (default `true`)
3. `statefulInput.includeZeroQuantityPositions` (default `false`)

lotus-risk request to lotus-core:

1. `snapshot_mode=BASELINE`
2. `sections=["positions_baseline","instrument_enrichment","portfolio_totals"]`

### 3) Simulation

Caller provides identifiers for simulation context; lotus-risk orchestrates lotus-core simulation APIs and then sources baseline and projected state from lotus-core snapshot in `SIMULATION` mode.

Required:

1. `simulationInput.portfolioId`
2. `simulationInput.asOfDate`
3. `simulationInput.simulationChanges[]` (request delta set applied via lotus-core session changes API)

Optional:

1. `simulationInput.sessionId` (for iterative reuse)
2. `simulationInput.expectedVersion`
3. `simulationInput.reportingCurrency`
4. `simulationInput.startNewSession` (optional explicit reset control; default `false`)
5. `simulationInput.sessionTtlHours` (optional, used only when creating a new session)

lotus-risk orchestration with lotus-core:

1. Session lifecycle:
 - first call (no `sessionId`): lotus-risk creates session in lotus-core and returns `sessionId`.
 - iterative calls (`sessionId` provided): lotus-risk reuses same session.
 - reset path: caller omits `sessionId` or sets `startNewSession=true`; lotus-risk creates new session.
 - TTL policy for new sessions: use `sessionTtlHours` when provided, else lotus-core default.
2. Apply `simulationChanges[]` to the resolved session through lotus-core simulation changes APIs.
3. Request snapshot with:
 - `snapshot_mode=SIMULATION`
 - `simulation.session_id`
 - `sections=["positions_baseline","positions_projected","positions_delta","instrument_enrichment","portfolio_totals"]`
4. Use lotus-core returned baseline/projected states as the sole calculation inputs.

TTL validation and behavior:

1. `sessionTtlHours` must follow lotus-core bounds (`1..168`).
2. If `sessionId` is provided and `startNewSession` is not set, `sessionTtlHours` is rejected as invalid request combination (`400`).
3. Session expiry remains core-owned; lotus-risk surfaces expiry metadata to caller.

## Concentration Types (v1/v2 rollout)

### v1 required (PR-1)

1. `portfolioConcentration.hhi` (current/proposed/delta)
2. `singlePositionConcentration`:
 - top position weight
 - top N cumulative weight (configurable `topN`, default 10)

### v2 planned (PR-2, same endpoint)

1. `issuerConcentration` (group by canonical issuer key from enrichment/reference mapping)
2. `sectorConcentration` and `countryConcentration` (if enrichment coverage is complete and quality-gated)

If grouping attributes are missing in upstream enrichment, lotus-risk returns explicit partial-coverage diagnostics instead of silent fallback.

## Output Contract (target)

```json
{
  "sourceService": "lotus-risk",
  "inputMode": "simulation",
  "valuationContext": {
    "portfolioCurrency": "EUR",
    "reportingCurrency": "USD",
    "positionBasis": "market_value_base",
    "weightBasis": "total_market_value_base"
  },
  "portfolioConcentration": {
    "hhiCurrent": "0.1134",
    "hhiProposed": "0.1268",
    "hhiDelta": "0.0134"
  },
  "singlePositionConcentration": {
    "topPositionWeightCurrent": "0.0820",
    "topPositionWeightProposed": "0.0965",
    "topPositionWeightDelta": "0.0145",
    "topNCumulativeWeightCurrent": "0.4123",
    "topNCumulativeWeightProposed": "0.4551",
    "topNCumulativeWeightDelta": "0.0428",
    "topN": 10
  },
  "issuerConcentration": null,
  "metadata": {
    "correlationId": "uuid",
    "asOfDate": "2026-02-27",
    "portfolioId": "DEMO_DPM_EUR_001",
    "simulationSessionId": "SIM_0001",
    "simulationSessionVersion": 3,
    "sessionExpiresAt": "2026-02-28T10:30:00Z"
  }
}
```

## Core Integration Requirements

lotus-risk depends on lotus-core `core-snapshot` behaviors:

1. Deterministic baseline/projected/delta sections for same inputs.
2. `simulation.session_id` and optional `expected_version` support.
3. Explicit error mapping (`400`, `404`, `409`, `422`) and actionable detail.
4. Valuation context fields in response (`portfolio_currency`, `reporting_currency`, basis fields).

No concentration-specific API is required in lotus-core.

## Validation and Testing Strategy

1. Unit tests:
 - mode normalization and validation
 - stateless, stateful, simulation adapters
 - concentration calculations (HHI + single-position)
2. Integration tests:
 - stubbed lotus-core client for snapshot responses and error mapping
 - per-mode end-to-end handler tests
3. Contract tests:
 - OpenAPI example/schema parity
 - RFC-0067 inventory regeneration and validation

## Risks and Mitigations

1. Drift in upstream enrichment semantics:
 - mitigate with strict typed mapper and explicit unknown-field handling.
2. Simulation race/version drift:
 - use `expectedVersion` when provided and propagate `409` contractually.
3. Vocabulary drift:
 - gate with inventory sync and cross-app validator in lotus-platform.

## Implementation Status Report

Completed in `lotus-risk`:

1. Single concentration endpoint with canonical `inputMode` envelope (`stateless`, `stateful`, `simulation`).
2. Stateful + simulation orchestration via lotus-core integration contracts (`/simulation-sessions/*` and `/integration/.../core-snapshot`).
3. Simulation session lifecycle implemented with caller-managed `sessionId` reuse, optional `startNewSession`, optional `sessionTtlHours`, and session metadata returned.
4. v1 concentration outputs implemented:
 - HHI (`hhiCurrent`, `hhiProposed`, `hhiDelta`)
 - Single-position concentration (top position and top-N cumulative metrics)
5. RFC-0067 governance artifacts implemented:
 - OpenAPI documentation completeness and examples
 - no-alias guard
 - vocabulary inventory regeneration and validation
6. Legacy stateless payload compatibility removed; canonical payload shape is now mandatory.

Pending for full RFC scope:

1. `issuerConcentration` remains pending (v2 scope) because issuer grouping depends on a canonical issuer attribute in lotus-core snapshot enrichment contract.

## Approval Decisions

1. Single-endpoint strategy with explicit `inputMode`: approved.
2. API surface strategy: one concentration API endpoint only; implementation can be phased across two PRs.
3. Scope phasing:
 - PR-1: HHI + `singlePositionConcentration`
 - PR-2: `issuerConcentration` on the same endpoint
4. Numeric and rounding policy: follow central Lotus rounding/precision policy; no service-specific rounding divergence.
5. Simulation ownership boundary: callers interact only with lotus-risk; lotus-risk orchestrates lotus-core and always calculates using lotus-core-provided before/after states.
6. Simulation session lifecycle: caller owns `sessionId` awareness and reuses it for iterative workflows; lotus-risk creates new session when `sessionId` is omitted (or `startNewSession=true`).
