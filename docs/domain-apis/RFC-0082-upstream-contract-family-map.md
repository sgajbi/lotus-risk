# RFC-0082 Upstream Contract Family Map

This document records how `lotus-risk` consumes upstream `lotus-core` and `lotus-performance`
contracts under platform RFC-0082.

It is consumer-conformance evidence for:

1. `C:/Users/Sandeep/projects/lotus-platform/rfcs/RFC-0082-lotus-core-domain-authority-and-analytics-serving-boundary-hardening.md`
2. `C:/Users/Sandeep/projects/lotus-core/docs/architecture/RFC-0082-contract-family-inventory.md`

## Current Integration Posture

`lotus-risk` remains the risk analytics authority. It owns portfolio risk metrics, drawdown,
rolling risk, historical attribution, concentration analytics, decomposition payloads, risk audit
lineage, and supportability semantics.

`lotus-performance` provides performance-aligned return series and benchmark exposure context for
stateful risk workflows.

`lotus-core` provides source-of-record portfolio snapshots, simulation sessions, instrument
enrichment, position analytics history, risk-free reference series, and related core source data.

Current transport posture remains REST/OpenAPI through `LOTUS_CORE_BASE_URL` and
`LOTUS_PERFORMANCE_BASE_URL`. There is no current gRPC contract between `lotus-risk`, `lotus-core`,
or `lotus-performance`.

## Upstream Client Surfaces

Implementation entrypoints:

1. `src/app/integrations/lotus_core_client.py`
2. `src/app/integrations/lotus_performance_client.py`
3. `src/app/services/risk_mode_adapter.py`
4. `src/app/services/drawdown_mode_adapter.py`
5. `src/app/services/rolling_mode_adapter.py`
6. `src/app/services/attribution_mode_adapter.py`
7. `src/app/services/benchmark_exposure_history.py`
8. `src/app/services/concentration_engine.py`

## `lotus-core` Contract Family Mapping

| `lotus-risk` client method | Upstream `lotus-core` route | RFC-0082 family | Current usage |
| --- | --- | --- | --- |
| `get_core_snapshot` | `POST /integration/portfolios/{portfolio_id}/core-snapshot` | Snapshot/simulation | Stateful concentration baseline, rolling Sharpe reporting-currency resolution, valuation context |
| `create_simulation_session` | `POST /simulation-sessions` | Snapshot/simulation | Concentration-only simulation mode setup |
| `add_simulation_changes` | `POST /simulation-sessions/{session_id}/changes` | Snapshot/simulation | Concentration-only simulation changes |
| `get_position_analytics_timeseries` | `POST /integration/portfolios/{portfolio_id}/analytics/position-timeseries` | Analytics input | Historical risk attribution exposure history |
| `get_instrument_enrichment` | `POST /integration/instruments/enrichment-bulk` | Analytics input watchlist | Issuer, sector, asset-class, and instrument enrichment for concentration and attribution |
| `get_risk_free_series` | `POST /integration/reference/risk-free-series` | Analytics input watchlist | Rolling Sharpe and risk-free reference sourcing |
| `get_risk_free_coverage` | `POST /integration/reference/risk-free-series/coverage?currency={currency}` | Support/coverage metadata | Coverage diagnostics when risk-free sourcing fails or is empty |

## `lotus-performance` Contract Mapping

| `lotus-risk` client method | Upstream `lotus-performance` route | Authority family | Current usage |
| --- | --- | --- | --- |
| `get_returns_series` | `POST /integration/returns/series` plus async polling when accepted | Performance analytics output/input to risk | Stateful risk calculate, drawdown, rolling metrics, and historical attribution return sourcing |
| `get_benchmark_exposure_context` | `POST /integration/benchmarks/exposure-context` | Performance-aligned benchmark exposure view | Historical active-risk attribution where benchmark exposures must align to performance returns |

`lotus-performance` owns the return and benchmark exposure semantics above. `lotus-risk` consumes
those outputs as inputs to risk analytics; it must not reconstruct performance returns locally when
stateful mode is requested.

## Consumer Conformance Rules

`lotus-risk` must keep these rules true:

1. risk analytics conclusions stay in `lotus-risk`;
2. performance return and benchmark exposure authority stays in `lotus-performance`;
3. canonical portfolio, instrument, simulation, and reference-data authority stays in `lotus-core`;
4. stateful risk workflows consume governed REST/OpenAPI contracts, not direct databases or inferred private contracts;
5. upstream failures remain mapped to deterministic Lotus error codes and structured categories;
6. signed VaR semantics, attribution reconciliation fields, issuer active-risk gating, concentration-only simulation support, and audit lineage metadata remain preserved for downstream consumers;
7. watchlist routes from `lotus-core` require explicit RFC-0082 review before their semantics are expanded.

## Existing Conformance Evidence

Current test and implementation evidence:

1. `tests/unit/test_lotus_core_client.py`
   Verifies core client routes, payload handling, and upstream error mapping.
2. `tests/unit/test_lotus_performance_client.py`
   Verifies returns-series, async result polling, benchmark exposure context, and upstream error mapping.
3. `tests/integration/test_risk_calculate.py`
   Verifies stateful risk calculation sources returns from `lotus-performance`.
4. `tests/integration/test_rolling_metrics_endpoint.py`
   Verifies rolling metrics use `lotus-performance` returns and `lotus-core` risk-free/reference inputs.
5. `tests/integration/test_historical_attribution_endpoint.py`
   Verifies historical attribution uses `lotus-performance` returns and benchmark exposure context plus `lotus-core` exposure/enrichment inputs.
6. `tests/integration/test_concentration_lotus_core_characterization.py`
   Verifies concentration stateful and simulation workflows use `lotus-core` snapshot and simulation contracts.
7. `docs/domain-apis/risk-upstream-failure-behavior.md`
   Documents deterministic upstream failure semantics for `lotus-core` and `lotus-performance`.

## Current Gap Register

1. Stateful `ACTIVE_RISK + ISSUER` remains intentionally gated until benchmark issuer exposure semantics are approved.
2. Risk-free coverage remains data-dependent by currency and window; unsupported windows must fail or degrade explicitly rather than fabricating Sharpe inputs.
3. Transport optimization is deferred. The current concern is contract correctness and data authority, not gRPC adoption.
4. Any future direct `lotus-core` source-data expansion must be checked against the `lotus-core` RFC-0082 contract-family inventory first.

## Validation Lane

This document is docs-only consumer-conformance hardening. Minimum validation is Feature Lane docs proof plus
targeted upstream-client test review.

Run code gates only when a future slice changes client behavior, request/response contracts, OpenAPI output,
or runtime coupling.
