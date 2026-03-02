# Rolling Metric Methodology - Rolling Information Ratio

## Metric
- metric_id: ROLLING_INFORMATION_RATIO

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Benchmark returns

## Upstream Data Sources
- Stateless: caller
- Stateful: lotus-performance

## Methodology and Formulas
- active_t = Rp_t - Rb_t
- rolling_mean(active)/rolling_std(active)*sqrt(annualization_basis)

## Configuration Options
- window_lengths
- annualization_basis

## Outputs
- window_results[].metric_summaries.ROLLING_INFORMATION_RATIO
- quality flag metric:ROLLING_INFORMATION_RATIO:zero_tracking_error_window

## Worked Example
- Computed per rolling window on active return stream
