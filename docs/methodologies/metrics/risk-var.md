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

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- HISTORICAL: percentile(alpha)
- GAUSSIAN: mean + std*z_alpha
- CORNISH_FISHER: adjusted z using skew/kurtosis
- scaled_var = base_var*sqrt(horizon_days)
- ES optional as tail mean

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: HISTORICAL: percentile(alpha)
4. Apply: GAUSSIAN: mean + std*z_alpha
5. Apply: CORNISH_FISHER: adjusted z using skew/kurtosis
6. Apply: scaled_var = base_var*sqrt(horizon_days)
7. Apply: ES optional as tail mean
8. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- options.var.method
- options.var.confidence
- options.var.horizon_days
- options.var.include_expected_shortfall

## Outputs
- results[period].metrics.VAR.value
- details.expected_shortfall when enabled

## Worked Example
Given:
- Returns [%]: [-2,-1,0,1,2], confidence=95%
- Historical VaR ~= -1.8, horizon=4 => -3.6
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

