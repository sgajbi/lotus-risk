# Lotus Risk Architecture

`lotus-risk` is the authoritative Lotus service for drawdown, rolling risk, attribution,
concentration, regime scenario-pack evaluation, risk-event cohorting, and mandate risk health
context.

## Current Architecture

The service is a FastAPI application under `src/app`. Domain-facing request and response contracts
live under `src/app/contracts`, business calculations and orchestration helpers live under
`src/app/services`, downstream adapters live under `src/app/integrations`, and cross-cutting
middleware/observability/error helpers live under dedicated app modules.

## Refactor Direction

1. Keep calculation logic in services and pure helpers.
2. Move route declarations out of `src/app/main.py` into focused routers.
3. Keep downstream HTTP clients behind service-facing protocols.
4. Keep middleware limited to correlation, audit, payload, policy, and telemetry concerns.
5. Preserve existing risk methodology behavior unless a change is explicitly documented and tested.

The initial quality baseline is recorded in `quality/baseline_report.md`.
