# RFC-0005: Rolling Risk Metrics Library (Industry-Grade, Historical-Only)

## Status

- Proposed
- Owner: lotus-risk
- Date: 2026-03-01

## Context

lotus-risk now provides institutional-grade concentration and realized drawdown analytics. The next priority is a reusable rolling risk metrics capability that supports private banking and wealth management use cases over current/historical data only.

This RFC defines a production-grade API and methodology for rolling risk metrics, with strict alignment to:

- lotus-platform governance and bounded contexts
- RFC-0067 vocabulary and OpenAPI quality requirements
- test pyramid and contract-first engineering discipline

## Objectives

1. Provide rolling-window risk diagnostics that are deterministic, interpretable, and integration-ready.
2. Keep one canonical endpoint contract with consistent execution modes (`stateless`, `stateful`, simulation deferred).
3. Ensure methodology transparency with explicit assumptions, edge-case handling, and reproducibility metadata.
4. Establish a foundation for future historical attribution and stress replay work without introducing forward-looking model complexity in this slice.

## Non-Goals

1. Forward-looking scenario generation or Monte Carlo engines.
2. Intraday analytics (daily frequency is baseline for v1).
3. New data ownership in lotus-risk (upstream sourcing remains lotus-performance and lotus-core references).

## Domain Scope (v1)

Rolling metrics to include:

1. Rolling volatility (annualized)
2. Rolling Sharpe ratio (annualized excess return over risk-free)
3. Rolling beta (portfolio vs benchmark)
4. Rolling tracking error (portfolio minus benchmark, annualized)
5. Rolling information ratio (active return over tracking error)
6. Rolling max drawdown (window-contained realized max drawdown)

## Endpoint Contract (Proposed)

- Endpoint: `POST /analytics/risk/rolling-metrics`
- Envelope:
  - `input_mode`: `stateless | stateful | simulation`
  - `stateless_input`: required for `stateless`
  - `stateful_input`: required for `stateful`
  - `simulation_input`: reserved; rejected in v1 with deterministic error

### Stateless Inputs

- `scope`
  - `as_of_date`
  - `net_or_gross`
  - optional client context fields
- `periods[]`
- `returns[]` (portfolio returns, percentage points)
- `benchmark_returns[]` (optional where metric set requires it)
- `risk_free_returns[]` (optional where metric set requires it)
- `rolling_options`
  - `window_lengths[]` (for example 21/63/126/252)
  - `annualization_basis` (`252` default business-day convention)
  - `min_observations_policy` (`STRICT` or `ALLOW_PARTIAL`)
  - `alignment_policy` (`INNER_JOIN` default)
  - `include_time_series` (bool)
  - `metrics[]` requested

### Stateful Inputs

- `portfolio_id`
- `as_of_date`
- `client_id` (optional)
- `reporting_currency` (optional; defaults to portfolio/reporting standards)
- `net_or_gross`
- `periods[]`
- `rolling_options`
- `benchmark_ref` and `risk_free_ref` selectors as needed for sourcing

### Upstream Sourcing (Stateful)

lotus-risk calls lotus-performance integration contracts to source canonical aligned series. lotus-performance remains responsible for:

- portfolio returns series
- benchmark reference series
- risk-free series
- date alignment and lineage metadata needed for auditability

## Output Contract (Proposed)

- `source_service`
- `input_mode`
- `scope`
- `results[period_name]`
  - `start_date`
  - `end_date`
  - `series_count`
  - `window_results[]`
    - `window_length`
    - `metric_summaries`
      - `latest`
      - `average`
      - `min`
      - `max`
      - `percentiles` (p05/p50/p95)
    - `metric_series` (optional when `include_time_series=true`)
      - `date`
      - per-metric value fields
  - `quality_flags[]`
  - `error` (period-level deterministic error)
- `metadata`
  - `contract_version`
  - `methodology_version`
  - `annualization_basis`
  - `alignment_policy`
  - upstream lineage references

## Methodology (v1)

All formulas use decimal return internally; API value representation follows platform rounding policy.

1. Rolling volatility:
- sample standard deviation over window, annualized by `sqrt(annualization_basis)`.

2. Rolling Sharpe:
- mean(excess return) / std(excess return), annualized using conventional numerator/denominator scaling.
- excess return = portfolio return - risk-free return.

3. Rolling beta:
- covariance(portfolio, benchmark) / variance(benchmark).
- return `null` with quality flag when benchmark variance is zero.

4. Rolling tracking error:
- standard deviation of active return (portfolio - benchmark), annualized.

5. Rolling information ratio:
- mean(active return) / std(active return), annualized.
- return `null` with quality flag when denominator is zero.

6. Rolling max drawdown:
- computed within each rolling window from cumulative wealth path.

## Data Alignment and Validation Rules

1. Series alignment defaults to inner-join on dates.
2. Duplicate dates are rejected.
3. Missing required reference series for requested metrics returns deterministic validation errors.
4. Partial windows behavior is governed by `min_observations_policy`.
5. If metric prerequisites fail for a window, metric result is `null` with explicit quality flag, not silent coercion.

## Quality and Risk Controls

1. Full contract tests for request/response and mode gating.
2. Characterization tests for rolling engine edge cases:
- flat benchmark variance
- zero tracking error
- sparse risk-free series
- mixed missing dates
- short samples and boundary windows
3. Integration characterization tests for lotus-performance adapter behavior.
4. E2E smoke coverage for endpoint availability and canonical response shape.
5. OpenAPI quality gate and vocabulary inventory gate must pass.

## Delivery Slices

### Slice A (stateless first)

- Build rolling engine and stateless contract.
- Implement endpoint with `stateless` mode.
- Add characterization + contract tests.
- Publish docs and examples.

### Slice B (stateful integration)

- Wire lotus-performance adapter.
- Enforce upstream lineage metadata in response.
- Add integration characterization and e2e stateful tests.

### Slice C (simulation deferral contract)

- Keep `simulation` as explicit not-implemented contract response until historical simulation data contract is finalized.

## Prioritized Backlog (Post RFC-0005)

1. Historical Risk Attribution
- Brinson-like and factor-informed historical decomposition on realized returns.

2. Historical Stress Replay
- Replay against curated historical market episodes and portfolio composition history.

Both backlog items remain historical/current-data only and must follow the same RFC-0067 + contract-first governance pattern.

## Open Decisions

1. Standard default window set for PB/WM profiles (proposal: 21/63/126/252).
2. Whether annualization basis should permit 260 alongside 252.
3. Minimum required observations for strict mode (proposal: full window).
4. Extent of percentile summaries in v1 output (proposal: p05/p50/p95 only).

## Acceptance Criteria

1. Endpoint contract and docs approved with no vocabulary drift.
2. Methodology section complete enough for model review.
3. Test suite includes characterization, contract, integration (slice-dependent), and e2e smoke.
4. CI gates pass: lint, typing, tests, pyramid, coverage, OpenAPI quality, no-alias, vocabulary validation.
