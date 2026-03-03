# Risk Metric Methodology - Drawdown

## Metric
- metric_id: DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return observations in pp for the selected period.

## Upstream Data Sources
- Stateless caller returns.
- Stateful lotus-performance returns.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. `W_t = Π(1+r_t/100)`.
2. `P_t = cummax(W_t)`.
3. `DD_t = W_t/P_t - 1`.
4. Reported value: `min(DD_t) * 100` (pp).

## Step-by-Step Computation
1. Build wealth and running-peak paths.
2. Compute drawdown series.
3. Find trough and corresponding prior peak dates.
4. Return drawdown value and details map.

## Configuration Options
- `options.frequency`

## Outputs
- `results[period].metrics.DRAWDOWN.value`
- `results[period].metrics.DRAWDOWN.details.max_drawdown`
- `...peak_date`
- `...trough_date`

## Worked Example
- Returns pp `[10, -20, 5]`.
- Wealth path `[1.10, 0.88, 0.924]`; running peak `[1.10, 1.10, 1.10]`.
- Drawdown decimal path `[0.00, -0.20, -0.16]`.
- Minimum drawdown is `-0.20`; reported metric value is `-20.0` pp.
- Peak/trough dates are derived from peak-before-trough logic in details payload.
