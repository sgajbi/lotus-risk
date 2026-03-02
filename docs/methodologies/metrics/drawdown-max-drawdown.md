# Drawdown Methodology - Maximum Drawdown

## Metric
- metric_id: MAX_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series

## Upstream Data Sources
- Stateless: caller
- Stateful: lotus-performance portfolio_returns

## Methodology and Formulas
- wealth_t=Π(1+r_t)
- drawdown_t=wealth_t/cummax(wealth_t)-1
- MAX_DRAWDOWN=min(drawdown_t)

## Configuration Options
- analysis_options.duration_unit
- analysis_options.include_episode_list

## Outputs
- summary.max_drawdown
- max_drawdown_peak_date
- max_drawdown_trough_date
- max_drawdown_recovery_date

## Worked Example
- Returns(dec) [0.05,-0.10,0.02] => max drawdown=-0.10
