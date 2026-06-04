# Lotus Risk Refactor Health Report

## Current Slice

This slice establishes the report-only enterprise quality baseline and progressive gate scaffolding.

## Highest Priority Refactor Targets

| Rank | Target | Evidence | Next action |
| --- | --- | --- | --- |
| 1 | Contract model size | Largest files are API contract modules over 800 lines | Split reusable examples, metadata, and nested contract fragments where it improves readability |
| 2 | Largest remaining function | build_period_results has 61 lines | Extract focused helpers around the next service hotspot while preserving behavior with characterization tests |
| 3 | Concentration service boundaries | Simulation/stateless resolvers and response assembly remain the largest service areas | Tighten ports, source resolution, issuer aggregation, and response assembly boundaries |

## Progressive Gate Posture

1. Baseline/report-only: active in this slice.
2. Fail only new regressions: next stage after baseline artifacts are stable.
3. Enforce agreed thresholds: after monolithic routers and largest engines are reduced.
4. Enterprise-readiness gates: final stage once API, security, observability, and docs are certified.
