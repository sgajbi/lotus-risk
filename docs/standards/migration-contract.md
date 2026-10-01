# Migration Contract

- Service: lotus-risk
- Scenario-evaluation jobs use an Alembic-managed relational schema. The current head is
  `20261001_02`, which adds fenced claim/lease state to tenant-scoped immutable admissions.
  Runtime admission is disabled unless `LOTUS_RISK_SCENARIO_JOB_DATABASE_URL` is configured and
  has every mapped job column plus the primary and tenant/idempotency uniqueness constraints. This
  is a minimum compatibility check, not a revision equality check, so compatible future additions
  remain available. Request handling never applies migrations.
- Rollback policy: forward-fix only; no destructive rollback in shared environments.
- CI enforces migration contract smoke checks via `migration-smoke` and `migration-apply` targets.
  Both targets execute `scripts/migration_contract_check.py --mode alembic-sql`; they must verify
  one Alembic head and render the migration SQL without a live database.
