# Home

## Start Here

`lotus-risk` is the authoritative risk analytics service in Lotus.

Read in this order:

1. [Overview](./Overview.md)
2. [Architecture](./Architecture.md)
3. [Getting Started](./Getting-Started.md)
4. [Validation and CI](./Validation-and-CI.md)
5. [Integrations](./Integrations.md)

## Current Posture

The repo is already a real domain-service surface, not a skeleton. The current public contract is
small but important:

1. risk calculation,
2. realized drawdown,
3. rolling risk metrics,
4. historical risk attribution,
5. concentration analytics,
6. capability publication,
7. operational diagnostics.

The most important current limits are:

1. simulation is supported only for concentration,
2. stateful historical attribution remains `partial` because `ACTIVE_RISK + ISSUER` is gated,
3. live validation defaults to canonical portfolio `PB_SG_GLOBAL_BAL_001`,
4. broader enterprise claims require more seeded archetypes and evidence.

## What lotus-risk Owns

`lotus-risk` owns:

1. risk analytics calculations and contracts,
2. stateful and stateless execution paths,
3. concentration simulation support,
4. supportability and lineage metadata,
5. capability publication for downstream orchestration.

It does not own:

1. portfolio or holdings truth,
2. returns authority from `lotus-performance`,
3. snapshot and reference-data authority from `lotus-core`,
4. gateway composition or Workbench affordance logic.

## Read By Need

Use:

1. [Getting Started](./Getting-Started.md) for local bring-up,
2. [Development Workflow](./Development-Workflow.md) for the repo working loop,
3. [Validation and CI](./Validation-and-CI.md) for gate meanings,
4. [Operations Runbook](./Operations-Runbook.md) for health, readiness, and local upstreams,
5. [Integrations](./Integrations.md) for gateway/downstream contract rules,
6. [Security and Governance](./Security-and-Governance.md) for contract and supportability discipline,
7. [RFC Index](./RFC-Index.md) for local decision history,
8. [Roadmap](./Roadmap.md) for remaining gaps and rollout posture.

## Core Commands

```powershell
make install
make check
make ci
uvicorn src.app.main:app --reload --port 8130
docker compose up --build
```

## Source Documents

- `README.md`
- `REPOSITORY-ENGINEERING-CONTEXT.md`
- `docs/domain-apis/endpoint-matrix.md`
- `docs/domain-apis/risk-product-surface-alignment.md`
- `docs/operations/live-risk-validation-matrix.md`
- `docs/rfcs/README.md`
