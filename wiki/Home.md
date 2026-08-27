# Home

## Start Here

`lotus-risk` is the authoritative risk analytics service in Lotus.

Read in this order:

1. [Overview](Overview)
2. [Architecture](Architecture)
3. [API Surface](API-Surface)
4. [Getting Started](Getting-Started)
5. [Validation and CI](Validation-and-CI)
6. [Integrations](Integrations)

## Current Posture

The repo is already a real domain-service surface, not a skeleton. The current public contract is
small but important:

1. risk calculation,
2. realized drawdown,
3. rolling risk metrics,
4. historical risk attribution,
5. concentration analytics,
6. mandate risk health context,
7. governed regime scenario-pack evaluation,
8. risk-event affected-cohort evaluation,
9. capability publication,
10. operational diagnostics.

The most important current limits are:

1. simulation is supported only for concentration,
2. stateful `ACTIVE_RISK` attribution supports `POSITION`, `SECTOR`, `ASSET_CLASS`, and `ISSUER` grouping dimensions; `CUSTOM` grouping and attribution simulation remain unsupported,
3. live validation defaults to canonical portfolio `PB_SG_GLOBAL_BAL_001`,
4. broader enterprise claims require more seeded archetypes and evidence.

The most important operating rule for downstream teams is:

1. use `/integration/capabilities` and the endpoint matrix as the support contract,
2. do not infer workflow support from one successful endpoint response.

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

1. [Getting Started](Getting-Started) for local bring-up,
2. [Development Workflow](Development-Workflow) for the repo working loop,
3. [Validation and CI](Validation-and-CI) for gate meanings,
4. [Operations Runbook](Operations-Runbook) for health, readiness, and local upstreams,
5. [Integrations](Integrations) for gateway/downstream contract rules,
6. [Security and Governance](Security-and-Governance) for contract and supportability discipline,
7. [Supported Features](Supported-Features) for implementation-backed support and limits,
8. [RFC Index](RFC-Index) for local decision history,
9. [Roadmap](Roadmap) for remaining gaps and rollout posture,
10. [API Surface](API-Surface) for the published operations and the supportability vocabulary,
11. [Glossary](Glossary) for the risk terminology and where each metric's methodology lives.

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
- `docs/index.md`
- `docs/supported-features.md`
- `docs/domain-apis/endpoint-matrix.md`
- `docs/domain-apis/risk-product-surface-alignment.md`
- `docs/operations/live-risk-validation-matrix.md`
- `docs/rfcs/README.md`
