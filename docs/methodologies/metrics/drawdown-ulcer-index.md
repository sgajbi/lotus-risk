# Drawdown Methodology - Ulcer Index

## Metric
- metric_id: ULCER_INDEX

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
1. Build wealth path:
`W_t = Π(1 + r_t/100)`.
2. Build running peak:
`P_t = max(W_1..W_t)`.
3. Build drawdown path:
`DD_t = W_t / P_t - 1`.
4. Square drawdown observations:
`SQ_t = DD_t^2`.
5. Ulcer Index:
`UI = sqrt(mean(SQ_t))`.

## Step-by-Step Computation
1. Compute period drawdown series from the return path.
2. Square each drawdown observation so larger drawdowns are penalized more.
3. Take mean of squared drawdowns over the full period.
4. Apply square root to restore drawdown scale.
5. Return ulcer index as a non-negative decimal risk intensity measure.

## Configuration Options
- No dedicated metric knob.

## Outputs
- `results[period].summary.ulcer_index`

## Worked Example
- Use drawdown path `[0.0000,-0.1000,-0.0820,-0.0453]`.
- Square values: `[0.000000,0.010000,0.006724,0.002052]`.
- Mean square = `0.004694`.
- Ulcer Index = `sqrt(0.004694) = 0.0685`.
- Output is decimal drawdown intensity.
