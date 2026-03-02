# Rolling Metric Methodology - Rolling Tracking Error

## Metric
- metric_id: ROLLING_TRACKING_ERROR

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
- rolling_std(active)*sqrt(annualization_basis)

## Configuration Options
- window_lengths
- annualization_basis

## Outputs
- window_results[].metric_summaries.ROLLING_TRACKING_ERROR

## Worked Example
- Window=3 active(dec) [0.001,-0.002,0.001] => 0.0275
