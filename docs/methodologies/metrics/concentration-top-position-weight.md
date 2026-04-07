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
- Position inputs are non-negative portfolio amounts:
  - `market_value_base` when available
  - `quantity` as fallback when market value is unavailable
- Output weights are decimals in `[0, 1]`.

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
- No dedicated formula option exists beyond the underlying portfolio state:
  - `top_n` does not affect this metric
  - `include_cash_positions` and `include_zero_quantity_positions` can change the input universe

## Outputs
- `single_position_concentration.top_position_weight_current`
- `single_position_concentration.top_position_weight_proposed`
- `single_position_concentration.top_position_weight_delta`
- `single_position_concentration.top_position_current`
- `single_position_concentration.top_position_proposed`

## Worked Example
Values current `[50,30,20]`, proposed `[60,25,15]`.
| State | Weights | Selected Top Position | Top Position Weight |
|---|---|---|---:|
| Current | `[0.50,0.30,0.20]` | position 1 | `0.50` |
| Proposed | `[0.60,0.25,0.15]` | position 1 | `0.60` |
Delta: `0.60 - 0.50 = 0.10`.
Output mapping:
- `single_position_concentration.top_position_weight_current=0.50`
- `single_position_concentration.top_position_weight_proposed=0.60`
- `single_position_concentration.top_position_weight_delta=0.10`
- `single_position_concentration.top_position_current` identifies the current top position
