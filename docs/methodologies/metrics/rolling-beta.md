# Rolling Metric Methodology - Rolling Beta

## Metric
- metric_id: ROLLING_BETA

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Benchmark returns

## Upstream Data Sources
- Stateless: caller benchmark_returns[]
- Stateful: lotus-performance benchmark_returns

## Methodology and Formulas
- rolling_cov(portfolio,benchmark)/rolling_var(benchmark)

## Configuration Options
- window_lengths
- min_observations_policy
- alignment_policy INNER_JOIN

## Outputs
- window_results[].metric_summaries.ROLLING_BETA
- quality flag metric:ROLLING_BETA:benchmark_variance_zero

## Worked Example
- Portfolio ~1.5x benchmark over window => rolling beta ~1.5
