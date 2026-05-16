# Enterprise Readiness

- Service: lotus-risk
- Status: RFC-0008 baseline implemented for the lotus-risk-owned contract; unrestricted enterprise-bank production approval remains conditional on downstream product proof, broader live portfolio archetype evidence, and green merge governance.

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
- Historical attribution must preserve `total_value`, `reconciled_sum`, `residual`, and contributor rows together so downstream consumers do not overstate explainability.
- VaR and expected shortfall are signed return-threshold metrics unless a downstream consumer explicitly documents a positive-loss convention conversion.

## Reliability and Operations Baseline

- Service readiness is enforced with health checks, retry/timeout patterns, and runbook coverage for migration operations.
- Endpoint execution and direct upstream dependency calls expose Prometheus metrics for mode, outcome, failure category, operation, and duration.
- Stateful upstream calls must use canonical direct local validation ports: lotus-risk `8130`, lotus-performance `8002`, and the lotus-core query control-plane `8202`.

## Product-Surface Baseline

- Gateway and Workbench consumers must derive simulation and issuer active-risk affordances from `GET /integration/capabilities`.
- Concentration is the only simulation-enabled risk flow in the current contract.
- Stateful `ACTIVE_RISK + ISSUER` is supported through lotus-performance benchmark exposure context issuer groups; unsupported grouping posture now applies to `CUSTOM` stateful grouping.
- See `docs/domain-apis/risk-product-surface-alignment.md`.
