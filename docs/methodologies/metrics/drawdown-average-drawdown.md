# Drawdown Methodology - Average Drawdown

## Metric
- metric_id: AVERAGE_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Drawdown path derived from return series.

## Upstream Data Sources
- Derived by drawdown engine.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Build wealth path from returns:
`W_t = Π(1 + r_t/100)`.
2. Build running peak:
`P_t = max(W_1..W_t)`.
3. Build drawdown path:
`DD_t = W_t / P_t - 1`.
4. Select only underwater points:
`U = {DD_t | DD_t < 0}`.
5. Average drawdown:
`AVG_DD = mean(U)` if `U` is not empty, else `0`.

## Step-by-Step Computation
1. Resolve period and compute wealth/running-peak path from return series.
2. Convert path to drawdown observations (`DD_t`).
3. Filter drawdown values strictly below zero.
4. Compute arithmetic mean of filtered values.
5. If no underwater points exist, return `average_drawdown = 0.0`.

## Configuration Options
- No dedicated metric knob.

## Outputs
- `results[period].summary.average_drawdown`

## Worked Example
- Use drawdown path `[0.0000,-0.1000,-0.0820,-0.0453]`.
- Filter negative values: `[-0.1000,-0.0820,-0.0453]`.
- Average = `(-0.1000-0.0820-0.0453)/3 = -0.0758`.
- Output `average_drawdown=-0.0758`.
- If no negative values exist, output is `0.0`.
