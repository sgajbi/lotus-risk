# Durability and Consistency

- Service: lotus-risk
- Workflow: domain-workflow

## Durability Core Entities

- Core entities in risk workflows include position snapshots, valuation outputs, and reference data used for deterministic risk analytics.
- The service is read-only for core portfolio writes and does not persist transaction, cash, or
  ledger state. It does persist tenant-scoped immutable scenario-job admission records when the
  explicitly configured relational store is migrated.
- Fail fast and explicit failure behavior is required for invalid input and contract violations.

## Consistency Classification

- Consistency class: strong consistency for in-request calculations and deterministic replay over the same input payload.
- Eventual consistency is not used for the core risk calculation path in this service.

## Transaction and Atomicity Boundaries

- Stateless calculations retain a single request/response atomicity boundary. Scenario-job
  admission atomically commits tenant/key identity, canonical request digest, immutable JSON,
  code-defined pack revision, retention expiry, and initial `QUEUED` status in one transaction.
- A same-key changed digest is refused; a same-key same-digest replay returns the original job.
  The claim store atomically transitions only `QUEUED` or expired-lease `RUNNING` records to a
  fresh fenced `RUNNING` claim. A terminal failure requires the current claim token, so a stale
  claimant cannot overwrite a recovered attempt. This is a durable evaluator-ownership primitive,
  not an evaluator runtime: result persistence, pages, expiry cleanup, capacity and throughput
  claims remain unavailable.

## Idempotency for Write APIs

- Scenario-job admission requires exactly one admitted `X-Tenant-Id` and exactly one
  `Idempotency-Key`; duplicate raw values are refused before store construction, so a proxy cannot
  select durable ownership or replay identity by header ordering. Process-local replay caches are
  prohibited. The configured store is unavailable-by-default until an operator supplies a migrated
  database URL and explicit retention duration.
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
