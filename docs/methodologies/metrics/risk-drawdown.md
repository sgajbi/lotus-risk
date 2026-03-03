# Risk Metric Methodology - Drawdown

## Metric
- metric_id: DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series in pp for selected period.

## Upstream Data Sources
- Stateless caller returns; stateful lotus-performance returns.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when required: `r_decimal = r_pp / 100`.
- Output units are metric-specific (ratio, annualized pp, decimal drawdown, or HHI scale).

## Variable Dictionary
- `r_t_pp`: period return at index `t` in percentage points.
- `r_t = r_t_pp/100`: decimal return.
- `W_t`: cumulative wealth index.
- `P_t`: running peak wealth.
- `DD_t = W_t/P_t - 1`: drawdown decimal.
- `MDD_pp = min(DD_t)*100`: endpoint metric value in pp.

## Methodology and Formulas
1. Convert returns to decimal and build wealth path.
2. Build running peak path.
3. Compute drawdown path.
4. Select minimum drawdown and convert to pp output.

## Step-by-Step Computation
1. Resolve period and series.
2. Compute wealth/peak/drawdown.
3. Find min drawdown and peak/trough metadata.
4. Emit value and details.

## Validation and Failure Behavior
- Fewer than 2 observations -> `Insufficient data`.
- Value is non-positive in pp for this endpoint metric.

## Configuration Options
- `options.frequency`

## Outputs
- `results[period].metrics.DRAWDOWN.value`
- `results[period].metrics.DRAWDOWN.details.max_drawdown`
- `...details.peak_date`
- `...details.trough_date`

## Worked Example
Returns pp `[10,-20,5]`.
| Date | Return pp | Wealth | Peak | Drawdown (decimal) |
|---|---:|---:|---:|---:|
| Day1 | 10.0 | 1.1000 | 1.1000 | 0.0000 |
| Day2 | -20.0 | 0.8800 | 1.1000 | -0.2000 |
| Day3 | 5.0 | 0.9240 | 1.1000 | -0.1600 |
`MDD_pp = -0.2000 * 100 = -20.0`.
Output mapping: `results[period].metrics.DRAWDOWN.value=-20.0`.