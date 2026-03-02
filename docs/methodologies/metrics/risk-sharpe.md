# Risk Metric Methodology - Sharpe Ratio

## Metric
- metric_id: SHARPE

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series
- Risk-free settings

## Upstream Data Sources
- Stateless: caller returns[]
- Stateful: lotus-performance portfolio_returns

## Methodology and Formulas
- periodic_rf = (1+annual_rf)^(1/annual_factor)-1 for ANNUAL_RATE mode
- Sharpe = ((mean(r)-periodic_rf)/std(r))*sqrt(annual_factor)

## Configuration Options
- options.risk_free_mode
- options.risk_free_annual_rate
- options.frequency
- options.annualization_factor

## Outputs
- results[period].metrics.SHARPE.value
- details.error on zero volatility

## Worked Example
- mean=0.0005, std=0.01, annual_rf=0.02, annual_factor=252
- Sharpe ~= 0.67
