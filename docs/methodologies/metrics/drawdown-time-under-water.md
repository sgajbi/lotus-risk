# Drawdown Methodology - Time Under Water

## Metric
- metric_id: TIME_UNDER_WATER_DAYS

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Drawdown path over period.

## Upstream Data Sources
- Derived in drawdown engine.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Build wealth and running peak from period returns:
`W_t = Π(1 + r_t/100)`, `P_t = max(W_1..W_t)`.
2. Compute drawdown path:
`DD_t = W_t / P_t - 1`.
3. Time-under-water count:
`TUW = Σ I(DD_t < 0)` where `I` is indicator function.

## Step-by-Step Computation
1. Resolve period and compute drawdown path point-by-point.
2. For each observation date, mark whether portfolio is below prior peak (`DD_t < 0`).
3. Count all marked observations to get time under water.
4. Return integer count in summary payload.
5. This metric measures persistence of drawdown, not its depth.

## Configuration Options
- No dedicated metric knob.

## Outputs
- `results[period].summary.time_under_water_days`

## Worked Example
- Drawdown path `[0.0000,-0.1000,-0.0820,-0.0453]`.
- Count points where drawdown `< 0`.
- Negative points are 3 observations.
- Output `time_under_water_days = 3`.
- Count is path-based and independent of drawdown depth.
