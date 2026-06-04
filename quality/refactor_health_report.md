# Lotus Risk Refactor Health Report

## Current Slice

This slice establishes the report-only enterprise quality baseline and progressive gate scaffolding.

## Highest Priority Refactor Targets

| Rank | Target | Evidence | Next action |
| --- | --- | --- | --- |
| 1 | API entry point | src/app/main.py has 136 lines and 2 app decorators | Extract routers and dependency providers |
| 2 | Concentration module | Largest service and contract files are concentration-related | Split source resolution, issuer aggregation, and response assembly |
| 3 | Risk calculation engine | Largest function is calculate_risk at 284 lines | Extract per-metric calculators behind stable service API |

## Progressive Gate Posture

1. Baseline/report-only: active in this slice.
2. Fail only new regressions: next stage after baseline artifacts are stable.
3. Enforce agreed thresholds: after monolithic routers and largest engines are reduced.
4. Enterprise-readiness gates: final stage once API, security, observability, and docs are certified.
