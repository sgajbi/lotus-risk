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
  - `series_count`
  - `benchmark_series_count`
  - `aligned_benchmark_series_count`
  - `benchmark_context`
  - `risk_free_series_count`
  - `aligned_risk_free_series_count`
  - `risk_free_context`
  - `window_lengths_requested`
  - `window_lengths_emitted`
  - `window_results[]`
    - `window_length`
    - `metric_summaries`
      - `total_point_count`
      - `computed_point_count`
      - `coverage_ratio`
      - `min_observations_required`
      - `warmup_point_count`
      - `non_computed_point_count`
      - `post_warmup_gap_point_count`
      - `latest_observation_date`
    - `metric_series_context`
    - `metric_series` (optional)
  - `quality_flags[]`
  - `error`
- `metadata`
  - methodology and lineage references
  - top-level dependency intent:
    - `benchmark_context.requested`
    - `benchmark_context.requested_metrics`
    - `risk_free_context.requested`
    - `risk_free_context.requested_metrics`

## Governance Alignment

- Bounded context: aligned (`lotus-risk` owns analytics; no portfolio construction logic).
- Vocabulary: RFC-0067 canonical naming only.
- API behavior: deterministic validation and explicit quality flags.
- Test discipline: characterization + contract + integration + e2e smoke.

## Gaps / Decisions Required

1. Expand stateful lineage metadata in response contract (`source_window`, `data_quality`, `upstream_refs`).
2. Evaluate whether annualization basis should support both 252 and 260 in v2.
3. rolling Sharpe remains data-dependent on lotus-core risk-free availability for the resolved currency/window. Live validation confirmed the lotus-core contract is reachable but returned no risk-free points for tested USD/SGD windows.
4. When lotus-core returns an empty risk-free series, lotus-risk now enriches the `424 FAILED_DEPENDENCY` error details with coverage diagnostics from `/integration/reference/risk-free-series/coverage` when available:
   - `risk_free_currency`
   - `risk_free_total_points`
   - `risk_free_missing_dates_count`
   - `risk_free_observed_start_date`
   - `risk_free_observed_end_date`
   - `risk_free_missing_dates_sample`
   - `risk_free_coverage_request_fingerprint`
