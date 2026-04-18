# Architecture

## Application Shape

`lotus-risk` is a FastAPI service with three practical endpoint families:

1. operational endpoints,
2. integration capability publication,
3. domain risk analytics endpoints.

That split is visible directly in `src/app/main.py`.

## Core Endpoint Groups

### Operational surface

1. `/health`
2. `/health/live`
3. `/health/ready`
4. `/metadata`
5. `/ops`
6. `/metrics`

### Integration surface

1. `/integration/capabilities`

This is the cross-service support contract. It publishes:

1. supported input modes,
2. workflow support levels,
3. notes about partial or intentionally unsupported behavior.

### Risk analytics surface

1. `/analytics/risk/calculate`
2. `/analytics/risk/drawdown`
3. `/analytics/risk/rolling-metrics`
4. `/analytics/risk/historical-attribution`
5. `/analytics/risk/concentration`

## Code Map

Primary implementation areas:

1. `src/app/contracts/`
   typed request and response models for each workflow.
2. `src/app/services/`
   analytics engines and stateful mode adapters.
3. `src/app/integrations/`
   upstream clients for `lotus-core` and `lotus-performance`.
4. `src/app/ops_runtime.py`
   readiness and ops-status evaluation.
5. `src/app/enterprise_readiness.py`
   enterprise-runtime validation and audit middleware setup.

## Execution Modes

The service supports three input-mode concepts across the estate:

1. `stateless`
2. `stateful`
3. `simulation`

The important rule is that support is workflow-specific, not service-wide:

1. concentration supports all three,
2. risk/calculate, drawdown, and rolling support stateless and stateful only,
3. historical attribution supports stateless and stateful, but stateful active-risk remains partially gated.

## Upstream Dependency Model

Stateful execution depends on governed upstream contracts:

1. `lotus-performance` for returns and benchmark context,
2. `lotus-core` for snapshots, simulation inputs, enrichment, and risk-free series.

## Product-Surface Contract

The architecture is not complete at calculation correctness alone. It also requires downstream
semantic preservation:

1. signed VaR must stay signed,
2. attribution residual and reconciled sum must stay attached to contributors,
3. unsupported issuer active-risk must remain visibly gated,
4. simulation must remain concentration-only,
5. lineage and upstream fingerprint metadata must survive downstream shaping.

## Read Next

1. use [Integrations](./Integrations.md) for the downstream contract view,
2. use [Operations Runbook](./Operations-Runbook.md) for runtime behavior,
3. use [Security and Governance](./Security-and-Governance.md) for why these boundaries are strict.
