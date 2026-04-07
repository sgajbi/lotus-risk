# Rolling Risk Metrics API Assessment

## Endpoint

- `POST /analytics/risk/rolling-metrics`

## Purpose

Provide windowed historical risk diagnostics for PB/WM portfolios with institutional-grade controls and transparent methodology.

## Execution Modes

### Stateless (v1)

- Status: implemented
- Caller provides portfolio and optional reference series directly.

### Stateful (v1)

- Status: implemented
- Caller provides identifiers and options; lotus-risk sources portfolio and benchmark return series from lotus-performance.
- lotus-risk resolves the longest required source window from the requested periods and sends an explicit `window` to lotus-performance unless `SI` is requested.
- when `ROLLING_SHARPE` is requested, lotus-risk sources risk-free reference series from lotus-core.
- when `ROLLING_SHARPE` is requested and `reporting_currency` is omitted, lotus-risk resolves portfolio/reporting currency from lotus-core core-snapshot before fetching risk-free series.

### Simulation

- Status: intentionally unsupported in the current production contract
- Reason:
  - rolling analytics require realized historical return windows
  - a projected holdings snapshot does not produce a valid historical rolling series

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
  - alignment/lineage metadata

- lotus-core:
  - risk-free reference series
  - direct `core-snapshot` lookup for portfolio/reporting currency when stateful rolling Sharpe requires risk-free series and caller omitted `reporting_currency`

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

1. Expand stateful lineage metadata in response contract (`source_window`, `data_quality`, `upstream_refs`).
2. Evaluate whether annualization basis should support both 252 and 260 in v2.
3. Confirm final benchmark/risk-free selector standardization in upstream contracts.
4. rolling Sharpe remains data-dependent on lotus-core risk-free availability for the resolved currency/window.
