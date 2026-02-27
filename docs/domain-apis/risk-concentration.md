# Concentration API Integration Guide

## Endpoint

- `POST /analytics/risk/concentration`

## Purpose

Compute concentration analytics using one canonical API contract across three execution modes.

Returned analytics blocks:

1. Portfolio concentration (`riskProxy`):
 - `hhiCurrent`
 - `hhiProposed`
 - `hhiDelta`
2. Single-position concentration:
 - top position weight
 - top-N cumulative weight
3. Issuer concentration:
 - issuer HHI current/proposed/delta
 - top issuer weight current/proposed/delta
 - coverage diagnostics

## Execution Modes

### Stateless

Caller supplies `currentPositions` and `projectedPositions` directly in `statelessInput`.

### Stateful

Caller supplies identifiers in `statefulInput` (`portfolioId`, `asOfDate`, optional policy fields).
`lotus-risk` sources baseline positions from lotus-core `core-snapshot` (`BASELINE` mode).

### Simulation

Caller supplies simulation context in `simulationInput`.
`lotus-risk` orchestrates lotus-core simulation session APIs, then pulls baseline/projected positions from `core-snapshot` (`SIMULATION` mode).

## Request Methodology

### Canonical envelope

```json
{
  "inputMode": "stateless | stateful | simulation",
  "statelessInput": {},
  "statefulInput": {},
  "simulationInput": {},
  "issuerGroupingLevel": "ultimate_parent | legal_issuer",
  "enrichmentPolicy": "merge_caller_then_core | use_caller_only | core_only"
}
```

Legacy top-level payload aliases are not supported.

### Issuer flags

1. `issuerGroupingLevel`
 - `ultimate_parent` (default)
 - `legal_issuer`
2. `enrichmentPolicy`
 - `merge_caller_then_core` (default): caller mappings override, core fills missing
 - `use_caller_only`: only caller issuer mappings are used
 - `core_only`: only lotus-core enrichment is used

### Caller enrichment options

1. Stateless:
 - positions can include `issuerId` and `ultimateParentIssuerId`
 - if missing and policy permits, lotus-risk calls lotus-core enrichment for missing mappings
2. Stateful/simulation:
 - caller can pass `issuerMappings[]` keyed by `securityId`
 - lotus-core `instrument_enrichment` remains the primary source

## Engine Behavior

### HHI computation

For any input set, HHI is computed from positive market values (fallback: positive quantities):

- weight_i = abs(value_i) / sum(abs(value))
- HHI = sum(weight_i^2) * 10000

### Single-position concentration

1. top position weight
2. top-N cumulative weight (`topN`, default `10`)

### Issuer concentration

1. Group positions by issuer key per `issuerGroupingLevel`.
2. Compute issuer-level HHI on grouped totals.
3. Compute top issuer weight.
4. Emit coverage diagnostics:
 - `coverageStatus` = `complete | partial | unavailable`
 - covered/total counts
 - optional `note`

No silent fallback is allowed when issuer mappings are missing.

## Simulation Session Behavior

1. First call without `sessionId`: lotus-risk creates lotus-core session and returns metadata.
2. Iterative calls with `sessionId`: lotus-risk reuses existing session.
3. Reset: omit `sessionId` or set `startNewSession=true`.
4. `sessionTtlHours` is allowed only for new sessions and must be within `1..168`.

### Iterative change semantics (normative)

1. `simulationChanges[]` is treated as the delta payload for the current call.
2. lotus-risk forwards these changes to lotus-core session changes API for the resolved session.
3. Changes are additive at session level unless the caller starts a new session.
4. Use `expectedVersion` to guard against concurrent edits on the same session.
5. Response includes:
 - `simulationSessionId`
 - `simulationSessionVersion`
 - `sessionExpiresAt` (when available)

### Recommended caller workflow

1. Initial simulation:
 - omit `sessionId`
 - optionally set `sessionTtlHours`
 - send first `simulationChanges[]`
2. Continue simulation:
 - pass returned `sessionId`
 - send incremental `simulationChanges[]`
 - optionally pass `expectedVersion` from previous response
3. Restart scenario:
 - set `startNewSession=true` (or omit `sessionId`)
 - send fresh `simulationChanges[]`

## Integration Dependencies

### Required from lotus-core

1. `POST /integration/portfolios/{portfolio_id}/core-snapshot`
 - baseline/projected positions + instrument enrichment
2. `POST /simulation-sessions`
3. `POST /simulation-sessions/{session_id}/changes`
4. (for stateless enrichment fallback) bulk enrichment endpoint for security list

## Output Coverage Semantics

`issuerConcentration` is always present. If mappings are incomplete:

1. values are computed on covered subset
2. coverage fields communicate quality
3. `note` explains why coverage is partial/unavailable
