# Supported Features

## Current Implementation-Backed Capabilities

| Capability | Primary endpoint | Current status | Business use |
| --- | --- | --- | --- |
| Risk metrics | `/analytics/risk/calculate` | full for stateless and stateful modes | Portfolio volatility, drawdown, Sharpe, Sortino, VaR, beta, tracking error, and information-ratio review. |
| Drawdown analytics | `/analytics/risk/drawdown` | full for stateless and stateful modes | Realized drawdown, underwater period, and recovery analysis. |
| Rolling risk metrics | `/analytics/risk/rolling-metrics` | full for stateless and stateful modes | Rolling historical risk diagnostics for front-office review. |
| Concentration risk | `/analytics/risk/concentration` | full for stateless, stateful, and simulation modes | Position, issuer, and HHI concentration review, including what-if simulation support; non-empty simulation changes require `Idempotency-Key` for lotus-core replay/conflict enforcement. |
| Historical attribution | `/analytics/risk/historical-attribution` | partial | Historical total-risk and active-risk decomposition; stateful `ACTIVE_RISK + ISSUER` is supported. |
| Regime scenario pack | `/analytics/risk/regime-scenario-pack/evaluate` | full stateless | CIO-governed scenario-pack evaluation with threshold posture and optional per-security contribution evidence. |
| Risk-event affected cohort | `/analytics/risk/risk-event-cohorts/evaluate` | partial stateless first-wave product | Source-owned portfolio membership and impact scores for governed risk events. |
| Mandate risk health | `/analytics/risk/mandate-health-context` | partial stateless first-wave product | Tracking-error health posture for downstream mandate-management consumption. |
| Idea opportunity producer proof | `make idea-opportunity-runtime-evidence` | source-safe producer evidence | Risk-owned runtime receipts for Idea RFC-0002 Slice 16/17; clears only Risk source-proof blockers and does not certify Idea persistence, data mesh, Gateway/Workbench, client publication, deployment, production, or supported-feature promotion. |
| Capability publication | `/integration/capabilities` | implemented | Downstream discovery of workflow support, mode support, and support notes; executable mode affordances come from workflow entries, not the top-level aggregate mode inventory. |
| Operations and observability | `/health`, `/health/ready`, `/ops`, `/metrics` | implemented | Runtime readiness, configured-only dependency posture, explicit dependency override states, and bounded Prometheus monitoring. |

## Explicit Limits

1. Simulation is supported only for concentration risk.
2. Concentration simulation `expected_version` is optimistic concurrency, not replay protection.
3. `CUSTOM` stateful historical-attribution grouping remains unsupported.
4. Mandate health context does not create mandate actions, rebalance waves, orders, execution, or
   client communications.
5. Risk-event affected cohorts do not create waves, approvals, campaigns, or client communications.
6. `/ops/trust-telemetry` returns repo-owned raw telemetry seeds; platform certification is a
   separate `lotus-platform` evidence flow.
7. Broad enterprise-bank coverage requires seeded portfolio archetype evidence beyond
   `PB_SG_GLOBAL_BAL_001`.
8. Idea opportunity producer proof is source-safe Risk evidence only; official methodology remains
   in `lotus-risk`, while Idea candidate persistence and product-surface certification remain
   separate consumer-side proof.

## Implementation Evidence

Use these sources when a support claim is questioned:

1. `docs/supported-features.md`
2. `docs/domain-apis/endpoint-matrix.md`
3. `docs/domain-apis/integration-capabilities.md`
4. `src/app/services/capability_workflows.py`
5. `tests/unit/test_capabilities_contract.py`
6. `tests/unit/test_product_surface_alignment_contract.py`
7. `tests/unit/test_risk_event_cohort_api.py`
8. `tests/unit/test_mandate_health_context.py`

## Read Next

1. [Integrations](./Integrations.md) for downstream preservation rules.
2. [Operations Runbook](./Operations-Runbook.md) for support and readiness checks.
3. [Roadmap](./Roadmap.md) for planned work and known evidence gaps.
