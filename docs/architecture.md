# Lotus Risk Architecture

`lotus-risk` is the authoritative Lotus service for drawdown, rolling risk, attribution,
concentration, regime scenario-pack evaluation, risk-event cohorting, and mandate risk health
context.

## Current Architecture

The service is a FastAPI application under `src/app`. Domain-facing request and response contracts
live under `src/app/contracts`, business calculations and orchestration helpers live under
`src/app/services`, downstream adapters live under `src/app/integrations`, and cross-cutting
middleware/observability/error helpers live under dedicated app modules.
Service-layer code reaches concrete Prometheus-backed observability only through the sanctioned
`src/app/services/observability_ports.py` adapter, keeping methodology and supportability helpers
free of direct infrastructure imports.

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

## Contract Model Classification

`src/app/contracts` contains three kinds of models. Keep the distinction explicit when refactoring:

| Classification | Meaning | Current examples | Service-layer rule |
| --- | --- | --- | --- |
| Public API DTO | Transport request/response shape governed by OpenAPI compatibility | endpoint request envelopes, response envelopes, response driver DTOs such as concentration top-position and top-issuer drivers | Construct at router/application response-mapping boundaries; lower-level calculation helpers should not depend on these shapes |
| Shared application value | Stable internal value object currently published through contract facades for compatibility | `ReturnPoint`, request period values, supportability state objects, selected domain enums | May be used by services until a dedicated domain package exists; avoid adding transport-only metadata or aliases to these values |
| Compatibility facade | Re-export module that preserves legacy import paths while implementation is split into smaller contract modules | `app.contracts.risk`, `app.contracts.concentration`, `app.contracts.rolling` | Do not use facade convenience as permission to couple pure helpers to response DTO construction |

The concentration calculation path is the first representative DTO-boundary migration. Pure
concentration math now returns internal driver values from
`src/app/services/concentration/datamodels.py`; `response_builder.py` maps those values to the
public Pydantic response DTOs. This preserves JSON/OpenAPI compatibility while shrinking the blast
radius of future response-contract changes.

## Refactor Direction

1. Keep calculation logic in services and pure helpers.
2. Keep route declarations in focused router modules rather than the ASGI export file.
3. Keep downstream HTTP clients behind service-facing protocols.
4. Keep concrete downstream client construction in lifespan/runtime composition, not routers.
5. Keep middleware limited to correlation, audit, payload, policy, and telemetry concerns.
6. Preserve existing risk methodology behavior unless a change is explicitly documented and tested.
7. Keep service observability behind `app.services.observability_ports`; direct
   `app.services -> app.observability` imports are blocked by architecture tests/import-linter.
8. Keep public API response DTO construction out of lower-level calculation helpers; map internal
   application/domain values to public DTOs at the application response boundary.

The initial quality baseline is recorded in `quality/baseline_report.md`.
