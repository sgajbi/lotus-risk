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

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- periodic_rf = (1+annual_rf)^(1/annual_factor)-1 for ANNUAL_RATE mode
- Sharpe = ((mean(r)-periodic_rf)/std(r))*sqrt(annual_factor)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: periodic_rf = (1+annual_rf)^(1/annual_factor)-1 for ANNUAL_RATE mode
4. Apply: Sharpe = ((mean(r)-periodic_rf)/std(r))*sqrt(annual_factor)
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- options.risk_free_mode
- options.risk_free_annual_rate
- options.frequency
- options.annualization_factor

## Outputs
- results[period].metrics.SHARPE.value
- details.error on zero volatility

## Worked Example
Given:
- mean=0.0005, std=0.01, annual_rf=0.02, annual_factor=252
- Sharpe ~= 0.67
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

