# Lotus Risk Architecture

`lotus-risk` is the authoritative Lotus service for drawdown, rolling risk, attribution,
concentration, regime scenario-pack evaluation, risk-event cohorting, and mandate risk health
context.

## Current Architecture

The service is a FastAPI application under `src/app`. Domain-facing request and response contracts
live under `src/app/contracts`, business calculations and orchestration helpers live under
`src/app/services`, downstream adapters live under `src/app/integrations`, and cross-cutting
middleware/observability/error helpers live under dedicated app modules.

The application is assembled by `src/app/app_factory.py`, which registers correlation middleware,
enterprise audit/readiness controls, HTTP observation middleware, standard error handlers, and the
router modules under `src/app/routers/`.

Process-local runtime composition lives under `src/app/runtime`. FastAPI lifespan creates the
concrete `lotus-core` and `lotus-performance` clients with reusable HTTP pools; API routers receive
a typed `RuntimeDownstreamClients` dependency and resolve stateful ports from that boundary only.
If lifespan state is missing for a stateful endpoint, the app fails closed with
`RUNTIME_COMPOSITION_ERROR` instead of constructing per-request fallback clients.

## Runtime Surfaces

| Surface | Router or module | Purpose |
| --- | --- | --- |
| Operational endpoints | `src/app/routers/operational.py` | health, liveness, readiness, metadata, ops diagnostics, trust telemetry, capabilities, and Prometheus metrics |
| Risk calculation | `src/app/routers/risk_calculation.py` | portfolio risk metrics for stateless and stateful inputs |
| Drawdown | `src/app/routers/drawdown.py` | realized drawdown analytics |
| Rolling metrics | `src/app/routers/rolling.py` | rolling volatility, Sharpe, beta, tracking error, information ratio, and max drawdown |
| Concentration | `src/app/routers/concentration.py` | stateless, stateful, and simulation concentration analytics |
| Historical attribution | `src/app/routers/historical_attribution.py` | historical risk and active-risk attribution decomposition |
| Source-owned products | `src/app/routers/source_products.py` | mandate risk health context, regime scenario-pack evaluation, and risk-event affected cohort evaluation |

## Domain Boundaries

`lotus-risk` owns risk meaning, methodology, supportability posture, lineage, and the repo-native
domain data product declarations under `contracts/domain-data-products/`. It does not own
portfolio holdings, transactions, benchmark returns, or UI composition. Stateful calls use
`lotus-performance` for returns and benchmark exposure context and `lotus-core` for snapshots,
simulation inputs, enrichment, and risk-free reference data.

The service publishes raw local trust telemetry through `/ops/trust-telemetry` and static
repo-native fixtures under `contracts/trust-telemetry/`. Platform-certified mesh posture remains
owned by `lotus-platform` generated certification artifacts, not by this endpoint alone.

## Refactor Direction

1. Keep calculation logic in services and pure helpers.
2. Keep route declarations in focused router modules rather than the ASGI export file.
3. Keep downstream HTTP clients behind service-facing protocols.
4. Keep concrete downstream client construction in lifespan/runtime composition, not routers.
5. Keep middleware limited to correlation, audit, payload, policy, and telemetry concerns.
6. Preserve existing risk methodology behavior unless a change is explicitly documented and tested.

The initial quality baseline is recorded in `quality/baseline_report.md`.
