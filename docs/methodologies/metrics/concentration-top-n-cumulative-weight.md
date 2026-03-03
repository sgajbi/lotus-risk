# Concentration Methodology - Top-N Cumulative Weight

## Metric
- metric_id: TOP_N_CUMULATIVE_WEIGHT

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Position value vectors for current and proposed states.
- `top_n` parameter.

## Upstream Data Sources
- Same source path as concentration HHI.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when required: `r_decimal = r_pp / 100`.
- Output units are metric-specific (ratio, annualized pp, decimal drawdown, or HHI scale).

## Variable Dictionary
- `v_i`: position value.
- `w_i = |v_i|/sum|v|`.
- `w_(i)`: weights sorted descending.
- `N = top_n`.
- `TOP_N = sum_{i=1..N}(w_(i))`.
- `TOP_N_delta = TOP_N_proposed - TOP_N_current`.

## Methodology and Formulas
1. Compute normalized weights.
2. Sort descending.
3. Sum first N values for each state.
4. Compute delta.

## Step-by-Step Computation
1. Build current/proposed weight vectors.
2. Apply top-n aggregation.
3. Emit current/proposed/delta and top_n.

## Validation and Failure Behavior
- If `top_n` exceeds position count, sum all available weights.
- Zero denominator yields `0`.

## Configuration Options
- `concentration_options.top_n`

## Outputs
- `single_position_concentration.top_n_cumulative_weight_current`
- `..._proposed`
- `..._delta`
- `single_position_concentration.top_n`

## Worked Example
Current weights `[0.50,0.30,0.20]`, proposed `[0.60,0.25,0.15]`, `top_n=2`.
| State | Sorted Weights | Top-2 Cumulative Weight |
|---|---|---:|
| Current | `[0.50,0.30,0.20]` | `0.80` |
| Proposed | `[0.60,0.25,0.15]` | `0.85` |
Delta: `0.05`.
Output mapping: `..._current=0.80`, `..._proposed=0.85`, `..._delta=0.05`.