# Concentration Methodology - Top Position Weight

## Metric
- metric_id: TOP_POSITION_WEIGHT

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Position value vectors for current and proposed states.

## Upstream Data Sources
- Same source path as position HHI.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when required: `r_decimal = r_pp / 100`.
- Output units are metric-specific (ratio, annualized pp, decimal drawdown, or HHI scale).

## Variable Dictionary
- `v_i`: position value.
- `w_i = |v_i|/sum|v|`.
- `TOP_1 = max_i(w_i)`.
- `V = sum_i |v_i|`: absolute denominator for weight normalization.
- `TOP_1_current`, `TOP_1_proposed`, `TOP_1_delta`: output trio.

## Methodology and Formulas
1. Compute absolute-normalized weights for each state.
2. Select maximum weight for each state.
3. Compute delta between proposed and current top weights.

## Step-by-Step Computation
1. Build value vectors.
2. Normalize to absolute weights.
3. Take max weight per state.
4. Emit current/proposed/delta fields.

## Validation and Failure Behavior
- If denominator is zero, top weight returns `0`.
- Non-numeric position values are ignored/rejected upstream.

## Configuration Options
- No dedicated option beyond underlying position extraction.

## Outputs
- `single_position_concentration.top_position_weight_current`
- `single_position_concentration.top_position_weight_proposed`
- `single_position_concentration.top_position_weight_delta`

## Worked Example
Values current `[50,30,20]`, proposed `[60,25,15]`.
| State | Weights | Top Position Weight |
|---|---|---:|
| Current | `[0.50,0.30,0.20]` | `0.50` |
| Proposed | `[0.60,0.25,0.15]` | `0.60` |
Delta: `0.60 - 0.50 = 0.10`.
Output mapping: `top_position_weight_current=0.50`, `..._proposed=0.60`, `..._delta=0.10`.
