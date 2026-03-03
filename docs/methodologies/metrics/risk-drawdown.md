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

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- wealth_t = Π(1+r_t)
- peak_t = cummax(wealth_t)
- drawdown_t = wealth_t/peak_t - 1
- DRAWDOWN = min(drawdown_t)*100

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: wealth_t = Π(1+r_t)
4. Apply: peak_t = cummax(wealth_t)
5. Apply: drawdown_t = wealth_t/peak_t - 1
6. Apply: DRAWDOWN = min(drawdown_t)*100
7. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- options.frequency (resample before calculation)

## Outputs
- results[period].metrics.DRAWDOWN.value
- details.max_drawdown, peak_date, trough_date

## Worked Example
Given:
- Returns [%]: [10, -20, 5] => drawdown path [0, -0.2, -0.16]
- Max drawdown = -20.0
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

