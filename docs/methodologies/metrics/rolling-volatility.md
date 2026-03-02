# Rolling Metric Methodology - Rolling Volatility

## Metric
- metric_id: ROLLING_VOLATILITY

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- window_lengths[]

## Upstream Data Sources
- Stateless: caller returns[]
- Stateful: lotus-performance portfolio_returns

## Methodology and Formulas
- Convert returns to decimal
- rolling_std(window,ddof=1)*sqrt(annualization_basis)

## Configuration Options
- rolling_options.window_lengths
- rolling_options.annualization_basis
- rolling_options.min_observations_policy

## Outputs
- window_results[].metric_summaries.ROLLING_VOLATILITY
- optional metric_series

## Worked Example
- Window=3, returns(dec) [0.01,-0.02,0.015] => 0.3005 annualized
