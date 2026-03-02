# Rolling Metric Methodology - Rolling Sharpe

## Metric
- metric_id: ROLLING_SHARPE

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Risk-free returns

## Upstream Data Sources
- Stateless: caller risk_free_returns[]
- Stateful: lotus-performance risk_free_returns

## Methodology and Formulas
- active_t = portfolio_t - risk_free_t
- rolling_mean(active)/rolling_std(active)*sqrt(annualization_basis)

## Configuration Options
- window_lengths
- annualization_basis
- alignment_policy INNER_JOIN

## Outputs
- window_results[].metric_summaries.ROLLING_SHARPE
- quality flag metric:ROLLING_SHARPE:zero_volatility_window

## Worked Example
- Window=3 active(dec) [0.001,0.002,-0.001] => rolling Sharpe ~= 6.93
