# Overview

## Repository Role

`lotus-risk` is the Lotus domain-authoritative service for risk analytics.

It owns the analytics and contract meaning for:

1. portfolio risk metrics,
2. realized drawdown,
3. rolling historical risk diagnostics,
4. concentration analytics,
5. historical risk attribution,
6. mandate risk health context,
7. governed regime scenario-pack evaluation,
8. risk-event affected-cohort evaluation.

## What Makes This Repo Important

The service sits close to front-office-visible workflows. When the contract drifts here:

1. gateway payloads drift,
2. Workbench surfaces become misleading,
3. supportability claims stop matching reality,
4. downstream product decisions become analytically untrustworthy.

That is why this repo cares so much about:

1. explicit mode support,
2. signed VaR semantics,
3. attribution reconciliation fields,
4. issuer active-risk support metadata,
5. lineage and upstream fingerprint metadata.

One practical consequence follows from that:

1. the capability publication surface is part of the product contract,
2. downstream teams should treat it as authoritative for affordances and support state.

## Primary Workflows

The current domain workflows are:

1. risk snapshot analytics via `/analytics/risk/calculate`,
2. realized drawdown analytics via `/analytics/risk/drawdown`,
3. rolling historical risk metrics via `/analytics/risk/rolling-metrics`,
4. historical attribution analytics via `/analytics/risk/historical-attribution`,
5. concentration analytics via `/analytics/risk/concentration`,
6. governed regime scenario-pack evaluation via
   `/analytics/risk/regime-scenario-pack/evaluate`,
7. governed risk-event affected-cohort evaluation via
   `/analytics/risk/risk-event-cohorts/evaluate`.

Operational and integration surfaces also matter:

1. `/integration/capabilities`
2. `/health`
3. `/health/live`
4. `/health/ready`
5. `/metadata`
6. `/version`
7. `/ops`
8. `/metrics`

## Upstream Dependencies

`lotus-risk` is authoritative for risk analytics, but not fully self-sufficient for every stateful
workflow.

It depends on:

1. `lotus-performance` for portfolio returns, benchmark returns, and benchmark exposure context,
2. `lotus-core` for snapshot, simulation, enrichment, and risk-free reference contracts.

Those boundaries are governed and should stay explicit.

## Current Functional Limits

The current approved API surface is implementation-backed but intentionally bounded:

1. simulation is concentration-only,
2. historical attribution is partial even though stateful `ACTIVE_RISK + ISSUER` is supported,
3. mandate risk health context and risk-event affected cohorts are stateless first-wave products,
4. live portfolio-archetype proof remains broader-roadmap work beyond the canonical baseline.

Those limits are intentionally exposed rather than hidden:

1. request validation rejects unsupported modes and unsupported grouping shapes,
2. `/integration/capabilities` marks historical attribution as `partial`,
3. docs describe the gate,
4. live evidence covers the supported stateful groupings.

That is the pattern this repo should keep following:

1. expose unsupported behavior explicitly,
2. do not hide it behind generic service-level language,
3. make downstream misuse harder than downstream correctness.

## Read Next

1. use [Architecture](./Architecture.md) for code and endpoint shape,
2. use [Integrations](./Integrations.md) for downstream contract rules,
3. use [Supported Features](./Supported-Features.md) for current support and limitations,
4. use [Roadmap](./Roadmap.md) for remaining rollout and evidence gaps.
