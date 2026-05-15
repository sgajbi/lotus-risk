# Concentration Methodology - Top-N Cumulative Weight

## Metric
- metric_id: TOP_N_CUMULATIVE_WEIGHT
- source_product: ConcentrationRiskReport:v1
- methodology_version: concentration.top_n_cumulative_weight.v1

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation
- output_family: `single_position_concentration`

## Inputs
- Current position rows.
- Proposed position rows when the caller supplies or source state resolves a projected state.
- `top_n` from `stateless_input.top_n`, `stateful_input.top_n`, or `simulation_input.top_n`.
- The request contract constrains `top_n` to an integer in the inclusive range `1..50`.

## Upstream Data Sources
- Stateless mode uses caller-provided `stateless_input.current_positions` and
  `stateless_input.projected_positions`.
- Stateful mode requests a lotus-core baseline snapshot and uses `positions_baseline` for both
  current and proposed states.
- Simulation mode creates or reuses a lotus-core simulation session, applies requested changes,
  requests a simulation snapshot, and uses baseline positions as current state and projected
  positions as proposed state.
- There is no lotus-performance dependency for top-N cumulative weight.

## Unit Conventions
- Position inputs are portfolio amount-like values, not return percentages.
- Stateless current rows use `market_value_base` when present; otherwise they fall back to
  `quantity`.
- Stateless projected rows use `projected_market_value_base` when present; otherwise they fall
  back to `proposed_quantity`.
- Stateful and simulation snapshot rows use `market_value_base` when present; otherwise they fall
  back to `quantity`.
- Values are parsed through Decimal from the source value's string representation. Missing,
  non-numeric, zero, and negative values are excluded before weight construction.
- Output weights are decimal ratios in `[0, 1]` and are rounded to six decimal places by the
  service response.

## Variable Dictionary
- `N`: requested top-N integer from the mode input.
- `C`: current extracted positive numeric position values.
- `P`: proposed extracted positive numeric position values.
- `x_i`: one extracted positive current value in `C`.
- `y_i`: one extracted positive proposed value in `P`.
- `V_C = sum_i(abs(x_i))`: current absolute exposure denominator.
- `V_P = sum_i(abs(y_i))`: proposed absolute exposure denominator.
- `w_i_current = abs(x_i) / V_C` when `V_C > 0`.
- `w_i_proposed = abs(y_i) / V_P` when `V_P > 0`.
- `sort_desc(W)`: weights sorted from largest to smallest.
- `TOP_N_current_raw = sum(first N values of sort_desc(w_current))`.
- `TOP_N_proposed_raw = sum(first N values of sort_desc(w_proposed))`.
- `TOP_N_delta_raw = TOP_N_proposed_raw - TOP_N_current_raw`.
- `round6(z)`: Python `round(z, 6)` used by the service response.

## Methodology and Formulas
For each state:

1. Extract one positive numeric value per usable position row according to the mode-specific
   field precedence.
2. Compute the denominator:
   `V = sum(abs(v_i))`.
3. If `V <= 0`, set the top-N cumulative weight to `0.0`.
4. Otherwise compute normalized weights:
   `w_i = abs(v_i) / V`.
5. Sort weights descending:
   `W_sorted = sort_desc(w)`.
6. Sum the first `N` sorted weights:
   `TOP_N_raw = sum(W_sorted[0:N])`.
7. Emit:
   - `single_position_concentration.top_n_cumulative_weight_current = round6(TOP_N_current_raw)`
   - `single_position_concentration.top_n_cumulative_weight_proposed = round6(TOP_N_proposed_raw)`
   - `single_position_concentration.top_n_cumulative_weight_delta = round6(TOP_N_proposed_raw - TOP_N_current_raw)`
   - `single_position_concentration.top_n = N`

When no proposed values are available, the implemented service sets
`TOP_N_proposed_raw = TOP_N_current_raw`; the emitted delta is therefore `0.0`.

## Step-by-Step Computation
1. Resolve request mode.
2. Build current position entries:
   - stateless: caller current positions,
   - stateful: lotus-core baseline positions,
   - simulation: lotus-core baseline positions.
3. Build proposed position entries:
   - stateless: caller projected positions,
   - stateful: same baseline positions as current,
   - simulation: lotus-core projected positions when available.
4. For each row, parse the preferred value field, fall back to the secondary value field, and keep
   only positive numeric values.
5. Normalize current values into current position weights.
6. Normalize proposed values into proposed position weights, or reuse current top-N cumulative
   weight when proposed values are empty.
7. Sort each state's weights descending.
8. Sum at most `N` sorted weights for each state.
9. Compute proposed-minus-current delta.
10. Round each emitted top-N weight and delta to six decimal places.

## Validation and Failure Behavior
- `top_n` less than `1` or greater than `50` is rejected by the request contract before
  calculation.
- Empty current values produce
  `single_position_concentration.top_n_cumulative_weight_current = 0.0`.
- Empty proposed values do not create an error; proposed top-N cumulative weight falls back to
  current state.
- Missing, non-numeric, zero, and negative values are excluded from the value vector.
- A single valid position produces top-N cumulative weight `1.0` for any valid `N`.
- If `N` exceeds the number of valid positions, the service sums all available sorted weights.
- Equal weights across `M` valid positions produce top-N cumulative weight `min(N, M) / M`.
- Issuer enrichment coverage does not change
  `single_position_concentration.top_n_cumulative_weight_*`; issuer coverage applies to
  `issuer_concentration`, not single-position concentration.
- The endpoint may still emit degraded calculation supportability for issuer coverage gaps, but
  top-N cumulative weight remains calculated from the available position values.

## Configuration Options
- Direct formula option:
  - `top_n`
- Options that can change the source position universe:
  - `include_cash_positions`
  - `include_zero_quantity_positions`
  - `reporting_currency`
- Options that do not change the top-N cumulative formula:
  - `issuer_grouping_level`
  - `enrichment_policy`

## Outputs
- `single_position_concentration.top_n_cumulative_weight_current`
- `single_position_concentration.top_n_cumulative_weight_proposed`
- `single_position_concentration.top_n_cumulative_weight_delta`
- `single_position_concentration.top_n`

## Worked Example
Current values `[50, 30, 20]`; proposed values `[60, 25, 15]`; `top_n = 2`.

| State | Values | Denominator | Sorted Weights | Sum of First 2 | Top-N Cumulative Weight |
|---|---|---:|---|---|---:|
| Current | `[50, 30, 20]` | `100` | `[0.50, 0.30, 0.20]` | `0.50 + 0.30` | `0.80` |
| Proposed | `[60, 25, 15]` | `100` | `[0.60, 0.25, 0.15]` | `0.60 + 0.25` | `0.85` |

Delta:

`single_position_concentration.top_n_cumulative_weight_delta = 0.85 - 0.80 = 0.05`.

Output mapping:

- `single_position_concentration.top_n_cumulative_weight_current = 0.80`
- `single_position_concentration.top_n_cumulative_weight_proposed = 0.85`
- `single_position_concentration.top_n_cumulative_weight_delta = 0.05`
- `single_position_concentration.top_n = 2`
