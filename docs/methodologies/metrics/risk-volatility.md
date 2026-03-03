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

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- sigma = std(returns, ddof=1)
- VOLATILITY = sigma * sqrt(annualization_factor)
- If use_log_returns=true: transform r_t = ln(1+r_t)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: sigma = std(returns, ddof=1)
4. Apply: VOLATILITY = sigma * sqrt(annualization_factor)
5. Apply: If use_log_returns=true: transform r_t = ln(1+r_t)
6. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- options.frequency
- options.annualization_factor
- options.use_log_returns

## Outputs
- results[period].metrics.VOLATILITY.value
- details.error when insufficient data

## Worked Example
Given:
- Returns [%]: [1.0, -0.5, 0.2]
- std ~= 0.7506, annual_factor=252 => volatility ~= 11.92
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

