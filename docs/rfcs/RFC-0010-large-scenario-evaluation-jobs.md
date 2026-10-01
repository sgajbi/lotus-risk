# RFC-0010: Durable Large Scenario Evaluation Jobs

## Status

Proposed — implementation owner: `lotus-risk`, tracked by GitHub issue #336.

## Decision

Keep `POST /analytics/risk/regime-scenario-pack/evaluate` unchanged and bounded. Add a separate,
tenant-authorized job API for up to 1,000 supplied exposure components. The API persists an
immutable canonical request, scenario-pack revision and submitted input fingerprint before it
returns a job identity. A database-backed worker claims jobs transactionally, performs one
evaluation, and persists aggregate evidence plus contribution rows. Result reads are tenant-scoped
and cursor-paged; pages never recompute or renormalize contributions.

## Invariants

1. `Idempotency-Key` plus tenant and canonical request digest identifies one submission. A replay
   returns that job; the same key with a different digest is a conflict.
2. Submission, immutable input, scenario-pack revision, and initial `QUEUED` state commit in one
   transaction. A worker changes state only through a compare-and-set claim.
3. A claim has a lease. Recovery may reclaim only an expired lease; terminal success/failure is
   fenced by the claim token so a stale worker cannot overwrite a newer attempt.
4. Every output row is keyed by `(job_id, scenario_id, ordinal)` and written with the aggregate
   result in the terminal transaction. Reads require the submitting tenant and use a stable cursor
   over that immutable order.
5. The worker evaluates the persisted payload and persisted pack revision, never live caller data
   or a mutable catalog default. A missing revision is a terminal qualified failure, not a fallback.

## Contract Shape

`POST /analytics/risk/regime-scenario-pack/jobs` accepts the existing request shape and required
`X-Tenant-Id` and `Idempotency-Key`; it returns `202` with `job_id`, `QUEUED`, request fingerprint,
pack revision and expiry. `GET .../jobs/{job_id}` returns status, aggregate result and qualified
terminal failure. `GET .../jobs/{job_id}/contributions?cursor=&limit=` returns at most the declared
limit, stable `next_cursor`, and source-owned contribution rows. No caller may choose pack revision,
worker count, retry policy, or an unbounded page size.

## Storage and Operations

Use the repository-supported production relational store and an explicit migration; SQLite is only
an isolated integration-test implementation. The migration creates jobs, immutable inputs,
attempts and contribution rows with tenant/idempotency uniqueness, lease and expiry indexes. The
worker is an existing-service runtime component, not a new service. Metrics use only bounded
operation/state/reason labels. Retention removes expired evidence in a documented job; it never
silently turns an expired result into another tenant's result.

## Acceptance and Rollout

Implement in slices: (1) migration/store/idempotent submit and tenant reads; (2) claim, lease,
recovery and terminal fencing; (3) 1,000-component evaluation and stable pages; (4) PostgreSQL
concurrency/restart, measured workload, observability and consumer acceptance. Each slice preserves
the existing synchronous cap. Roll back by disabling job admission; retained immutable jobs remain
readable until their stated expiry.

### Implementation progress

Slices 1 through the durable execution portion of slice 3 are implemented: admission,
tenant-scoped status reads, transactional claim, expired-lease recovery, stale-token terminal
fencing, one-at-a-time worker evaluation, atomic aggregate success publication, and stable
tenant-scoped contribution pages. The synchronous route remains capped; the worker evaluates the
persisted 1,000-component request against its stored pack revision and does not recompute pages.
Bounded worker outcome and duration metrics distinguish idle, success, qualified refusal,
invalid persisted input, stale-fence rejection, and retryable error without durable identities.
Deployment retention policy, capacity measurement, deployment scheduling, and consumer acceptance
remain explicitly outstanding.

Before either job route receives traffic, operators must apply the current Alembic head. Runtime
does not auto-migrate: it verifies the complete mapped job schema and durable primary/idempotency
constraints, returning the documented unavailable response for an older or unreachable store.
Compatible future schema additions are accepted; revision labels are not used as an availability
shortcut.

## Non-goals

This does not ingest core-bank holdings, create orders, replace CIO scenario methodology, infer
tenant authority, add a service split, or claim horizontal scalability before measured evidence.
