# Concentration Analytics Endpoint Assessment

## Endpoint

- `POST /analytics/risk/concentration`

## Purpose

- Compute HHI-based concentration metrics for current and projected position quantities:
  - `hhiCurrent`
  - `hhiProposed`
  - `hhiDelta`

## Execution Mode Support

### Stateless

- Status: supported now.
- Behavior:
  - caller supplies position quantities directly.
  - lotus-risk computes concentration metrics with no internal upstream calls.

### Stateful

- Status: not implemented in lotus-risk.
- Target behavior:
  - caller provides identifiers (`portfolioId`, optional `sessionId`, etc.).
  - lotus-risk resolves current/projected positions from upstream Lotus services.

### Simulation

- Status: not implemented in lotus-risk.
- Target behavior:
  - baseline positions sourced internally from lotus-core.
  - overrides/scenario deltas applied by lotus-risk before HHI calculation.

## Stateless Inputs (Current)

- `currentPositions[]`
  - `securityId: str`
  - `quantity?: float`
- `projectedPositions[]`
  - `securityId: str`
  - `proposedQuantity?: float`

## Stateful/Simulation Input Source Mapping (Target)

| Input Needed | Preferred Source App | Availability | Notes |
|---|---|---|---|
| Current positions (quantities and asset metadata) | lotus-core core snapshot (`/integration/portfolios/{id}/core-snapshot`) | Exists | already used in gateway/reporting workflows. |
| Projected positions for active simulation | lotus-core simulation (`/simulation-sessions/{id}/projected-positions`) | Exists | currently orchestrated by lotus-gateway patterns. |
| Scenario overrides (trade/quantity deltas) | lotus-risk request schema | Needs enhancement | not defined in lotus-risk API today. |

## Expected Output Structure

- `sourceService: "lotus-risk"`
- `riskProxy`
  - `hhiCurrent: float`
  - `hhiProposed: float`
  - `hhiDelta: float`

## Alignment Assessment

- Bounded context ownership: aligned (concentration belongs to `lotus-risk` per RFC-0065).
- Current API correctness: aligned for stateless mode.
- Integration depth: incomplete for target stateful/simulation execution.

## Gaps and Decisions Required

1. Define stateful and simulation contracts for concentration endpoint (single endpoint with mode switch vs separate endpoints).
2. Decide source-of-truth precedence when both projected state and override payload are provided.
3. Define whether output should include additional breakdown metadata (for example concentration contributors/top issuers) under this endpoint or a separate risk exposure endpoint to keep bounded responsibilities clear.
