# Migration Contract

- Service: lotus-risk
- No persistent schema at current stage; this service runs in no-schema mode.
- Versioned migration contract is still required for future schema onboarding.
- Rollback policy: forward-fix only; no destructive rollback in shared environments.
- CI enforces migration contract smoke checks via `migration-smoke` and `migration-apply` targets.
  Both targets execute `scripts/migration_contract_check.py --mode no-schema`; they must not skip
  when legacy migration tests are absent or call stale DPM/Postgres migration scripts.
