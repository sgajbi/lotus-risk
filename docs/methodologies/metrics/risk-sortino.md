# Risk Metric Methodology - Sortino Ratio

## Metric
- metric_id: SORTINO

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series
- MAR annual rate

## Upstream Data Sources
- Stateless: caller returns[]
- Stateful: lotus-performance portfolio_returns

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- periodic_mar = (1+mar_annual_rate)^(1/annual_factor)-1
- downside = r_t-periodic_mar where downside<0
- Sortino = ((mean(r)-periodic_mar)/sqrt(mean(downside^2)))*sqrt(annual_factor)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: periodic_mar = (1+mar_annual_rate)^(1/annual_factor)-1
4. Apply: downside = r_t-periodic_mar where downside<0
5. Apply: Sortino = ((mean(r)-periodic_mar)/sqrt(mean(downside^2)))*sqrt(annual_factor)
6. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- options.mar_annual_rate
- options.frequency
- options.annualization_factor

## Outputs
- results[period].metrics.SORTINO.value
- details.error when downside observations missing

## Worked Example
Given:
- Returns(dec): [0.01,-0.02,0.005], MAR=0
- Sortino ~= -1.32
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

