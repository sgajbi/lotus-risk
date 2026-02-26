# Enterprise Readiness

- Service: lotus-risk
- Status: baseline adopted.

## Security and IAM Baseline

- Enterprise audit middleware captures privileged write actions with actor, tenant, role, and correlation identifiers.
- Sensitive and pii fields are redact/mask protected in audit metadata.

## API Governance Baseline

- OpenAPI contracts are versioned and compatibility/deprecation rules are documented and tested.

## Config and Feature Management Baseline

- Feature flag policy is driven by `ENTERPRISE_FEATURE_FLAGS_JSON`.
- Authorization is deny-by-default and fail closed when required identity headers or capabilities are missing.

## Data Quality and Reconciliation Baseline

- Request validation and schema checks enforce invariants.
- Reconciliation and quarantine handling are documented for invalid upstream data.

## Reliability and Operations Baseline

- Service readiness is enforced with health checks, retry/timeout patterns, and runbook coverage for migration operations.
