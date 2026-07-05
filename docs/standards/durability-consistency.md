# Durability and Consistency

- Service: lotus-risk
- Workflow: domain-workflow

## Durability Core Entities

- Core entities in risk workflows include position snapshots, valuation outputs, and reference data used for deterministic risk analytics.
- The service is read-only for core portfolio writes and does not persist transaction, cash, or ledger state.
- Fail fast and explicit failure behavior is required for invalid input and contract violations.

## Consistency Classification

- Consistency class: strong consistency for in-request calculations and deterministic replay over the same input payload.
- Eventual consistency is not used for the core risk calculation path in this service.

## Transaction and Atomicity Boundaries

- Atomicity boundary is a single request/response unit of work.
- No multi-step commit/rollback orchestration is performed because there is no persistent write transaction in lotus-risk.
- Compensation and retry semantics are delegated to upstream orchestrators.

## Idempotency for Write APIs

- Future write endpoints must require `Idempotency-Key` and enforce idempotency semantics for replay protection.
- Most analytics endpoints are read-oriented computations with no persistent side effects.
- Concentration simulation is the current exception: when `simulation_input.simulation_changes[]`
  is non-empty, `POST /analytics/risk/concentration` requires `Idempotency-Key` and forwards that
  key plus a deterministic change-set fingerprint to lotus-core for source-owned replay/conflict
  enforcement.
- `expected_version` remains optimistic concurrency for simulation snapshots; it is not replay
  protection.

## Governance Change Control

- Durability/consistency policy deviations require an ADR or RFC with explicit expiry review.
- Change control must document impact, rollback strategy, and approval evidence before release.
