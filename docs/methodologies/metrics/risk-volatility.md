# Risk Metric Methodology - Volatility

## Metric
- metric_id: VOLATILITY

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series for resolved period
- Annualization basis (frequency or override)

## Upstream Data Sources
- Stateless: caller returns[]
- Stateful: lotus-performance /integration/returns/series -> portfolio_returns

## Methodology and Formulas
- sigma = std(returns, ddof=1)
- VOLATILITY = sigma * sqrt(annualization_factor)
- If use_log_returns=true: transform r_t = ln(1+r_t)

## Configuration Options
- options.frequency
- options.annualization_factor
- options.use_log_returns

## Outputs
- results[period].metrics.VOLATILITY.value
- details.error when insufficient data

## Worked Example
- Returns [%]: [1.0, -0.5, 0.2]
- std ~= 0.7506, annual_factor=252 => volatility ~= 11.92
