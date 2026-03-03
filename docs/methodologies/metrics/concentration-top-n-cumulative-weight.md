# Concentration Methodology - Top-N Cumulative Weight

## Metric
- metric_id: TOP_N_CUMULATIVE_WEIGHT

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Position valuations and top_n.

## Upstream Data Sources
- Same as position concentration.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Compute normalized absolute weights `w_i` from position values.
2. Sort weights descending: `w_(1) >= w_(2) >= ...`.
3. Top-N cumulative metric: `TOP_N = sum_{i=1..N} w_(i)`.
4. Delta: `TOP_N_delta = TOP_N_proposed - TOP_N_current`.

## Step-by-Step Computation
1. Resolve weights for baseline and proposed states.
2. Sort each weight vector descending.
3. Sum first `N` entries using configured `top_n`.
4. Emit current/proposed/delta plus `top_n` used.

## Configuration Options
- `concentration_options.top_n`

## Outputs
- `single_position_concentration.top_n_cumulative_weight_current`
- `...proposed`
- `...delta`

## Worked Example
- Position values `[50, 30, 20]` -> weights `[0.50, 0.30, 0.20]`.
- With `top_n=2`, sort descending and sum first 2.
- Top-2 cumulative weight current = `0.50 + 0.30 = 0.80`.
- Proposed weights `[0.60,0.25,0.15]` give top-2 cumulative = `0.85`.
- Delta = `+0.05`.