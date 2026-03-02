# Risk Metric Methodology - Drawdown

## Metric
- metric_id: DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series for resolved period

## Upstream Data Sources
- Stateless: caller returns[]
- Stateful: lotus-performance portfolio_returns

## Methodology and Formulas
- wealth_t = Π(1+r_t)
- peak_t = cummax(wealth_t)
- drawdown_t = wealth_t/peak_t - 1
- DRAWDOWN = min(drawdown_t)*100

## Configuration Options
- options.frequency (resample before calculation)

## Outputs
- results[period].metrics.DRAWDOWN.value
- details.max_drawdown, peak_date, trough_date

## Worked Example
- Returns [%]: [10, -20, 5] => drawdown path [0, -0.2, -0.16]
- Max drawdown = -20.0
