# Rolling Risk Metrics API (Design Assessment)

## Endpoint

- `POST /analytics/risk/rolling-metrics` (proposed)

## Purpose

Provide windowed historical risk diagnostics for PB/WM portfolios with institutional-grade controls and transparent methodology.

## Execution Modes

### Stateless (v1)

- Status: planned in Slice A
- Caller provides portfolio and optional reference series directly.

### Stateful (v1)

- Status: planned in Slice B
- Caller provides identifiers and options; lotus-risk sources canonical series from lotus-performance.

### Simulation

- Status: deferred
- Contract kept explicit; deterministic not-implemented response in RFC-0005 scope.

## Required Inputs (By Capability)

1. Always required:
- `scope.as_of_date`
- `periods[]`
- `rolling_options.window_lengths[]`
- `rolling_options.metrics[]`

2. Required by metric:
- `rolling_volatility`: portfolio returns
- `rolling_max_drawdown`: portfolio returns
- `rolling_sharpe`: portfolio returns + risk-free returns
- `rolling_beta`: portfolio returns + benchmark returns
- `rolling_tracking_error`: portfolio returns + benchmark returns
- `rolling_information_ratio`: portfolio returns + benchmark returns

## Upstream Data Sources (Stateful)

- lotus-performance:
  - portfolio returns series
  - benchmark reference series
  - risk-free reference series
  - alignment/lineage metadata

- lotus-core:
  - indirect via lotus-performance `core_api_ref` where relevant to portfolio identity/context.

## Expected Output Structure

- `source_service`
- `input_mode`
- `scope`
- `results[period_name]`
  - `start_date`
  - `end_date`
  - `window_results[]`
    - `window_length`
    - `metric_summaries`
    - `metric_series` (optional)
  - `quality_flags[]`
  - `error`
- `metadata`
  - methodology and lineage references

## Governance Alignment

- Bounded context: aligned (`lotus-risk` owns analytics; no portfolio construction logic).
- Vocabulary: RFC-0067 canonical naming only.
- API behavior: deterministic validation and explicit quality flags.
- Test discipline: characterization + contract + integration + e2e smoke.

## Gaps / Decisions Required

1. Confirm default window set (proposal: 21/63/126/252).
2. Confirm annualization basis flexibility (252 only vs 252/260).
3. Confirm strict vs partial window policy defaults.
4. Confirm percentile summary set in v1.
