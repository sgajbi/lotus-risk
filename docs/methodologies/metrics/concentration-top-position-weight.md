# Concentration Methodology - Top Position Weight

## Metric
- metric_id: TOP_POSITION_WEIGHT

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Position valuations.

## Upstream Data Sources
- Same as concentration HHI path.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Compute absolute denominator: `V = sum_i |v_i|`.
2. Compute normalized weights: `w_i = |v_i| / V`.
3. Top position metric: `TOP_1 = max_i(w_i)`.
4. Delta: `TOP_1_delta = TOP_1_proposed - TOP_1_current`.

## Step-by-Step Computation
1. Build baseline and proposed value vectors from input positions.
2. Normalize vectors to absolute weights.
3. Select maximum weight in each state.
4. Compute delta and write response fields.

## Configuration Options
- No dedicated option.

## Outputs
- `single_position_concentration.top_position_weight_current`
- `...proposed`
- `...delta`

## Worked Example
- Position values `[50, 30, 20]` -> total `100`.
- Weights are `[0.50, 0.30, 0.20]`.
- Top position weight current = `0.50`.
- Proposed weights `[0.60,0.25,0.15]` -> top position `0.60`.
- Delta = `+0.10`.