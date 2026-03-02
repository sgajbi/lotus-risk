# Rolling Metric Methodology - Rolling Max Drawdown

## Metric
- metric_id: ROLLING_MAX_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- window_lengths[]

## Upstream Data Sources
- Stateless: caller
- Stateful: lotus-performance

## Methodology and Formulas
- For each rolling window: wealth=Π(1+r)
- drawdown=wealth/cummax(wealth)-1
- window metric=min(drawdown)

## Configuration Options
- window_lengths
- min_observations_policy

## Outputs
- window_results[].metric_summaries.ROLLING_MAX_DRAWDOWN

## Worked Example
- Window returns [0.02,-0.03,0.01] => rolling max drawdown ~ -0.03
