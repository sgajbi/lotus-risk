# Risk Metric Methodology - Value at Risk

## Metric
- metric_id: VAR

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series
- VaR method/confidence/horizon

## Upstream Data Sources
- Stateless: caller returns[]
- Stateful: lotus-performance portfolio_returns

## Methodology and Formulas
- HISTORICAL: percentile(alpha)
- GAUSSIAN: mean + std*z_alpha
- CORNISH_FISHER: adjusted z using skew/kurtosis
- scaled_var = base_var*sqrt(horizon_days)
- ES optional as tail mean

## Configuration Options
- options.var.method
- options.var.confidence
- options.var.horizon_days
- options.var.include_expected_shortfall

## Outputs
- results[period].metrics.VAR.value
- details.expected_shortfall when enabled

## Worked Example
- Returns [%]: [-2,-1,0,1,2], confidence=95%
- Historical VaR ~= -1.8, horizon=4 => -3.6
