# Concentration Methodology - Top Position Weight

## Metric
- metric_id: TOP_POSITION_WEIGHT
- source_product: ConcentrationRiskReport:v1
- methodology_version: concentration.top_position_weight.v1

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation
- output_family: `single_position_concentration`

## Inputs
- Current position rows.
- Proposed position rows when the caller supplies or source state resolves a projected state.
- Position `security_id` and `security_name` values are preserved in the top-position driver
  payloads when available.
- `top_n` is accepted by the endpoint for top-N cumulative concentration fields but does not
  change `TOP_POSITION_WEIGHT`.

## Upstream Data Sources
- Stateless mode uses caller-provided `stateless_input.current_positions` and
  `stateless_input.projected_positions`.
- Stateful mode requests a lotus-core baseline snapshot and uses `positions_baseline` for both
  current and proposed states.
- Simulation mode creates or reuses a lotus-core simulation session, applies requested changes,
  requests a simulation snapshot, and uses baseline positions as current state and projected
  positions as proposed state.
- There is no lotus-performance dependency for top-position weight.

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
- `C`: current extracted positive numeric position values.
- `P`: proposed extracted positive numeric position values.
- `x_i`: one extracted positive current value in `C`.
- `y_i`: one extracted positive proposed value in `P`.
- `V_C = sum_i(abs(x_i))`: current absolute exposure denominator.
- `V_P = sum_i(abs(y_i))`: proposed absolute exposure denominator.
- `w_i_current = abs(x_i) / V_C` when `V_C > 0`.
- `w_i_proposed = abs(y_i) / V_P` when `V_P > 0`.
- `TOP_current_raw = max_i(w_i_current)`.
- `TOP_proposed_raw = max_i(w_i_proposed)`.
- `TOP_delta_raw = TOP_proposed_raw - TOP_current_raw`.
- `round6(z)`: Python `round(z, 6)` used by the service response.

## Methodology and Formulas
For each state:

1. Extract one positive numeric value per usable position row according to the mode-specific
   field precedence.
2. Compute the denominator:
   `V = sum(abs(v_i))`.
3. If `V <= 0`, set the top-position weight to `0.0`.
4. Otherwise compute normalized weights:
   `w_i = abs(v_i) / V`.
5. Select the largest weight:
   `TOP_raw = max_i(w_i)`.
6. Emit:
   - `single_position_concentration.top_position_weight_current = round6(TOP_current_raw)`
   - `single_position_concentration.top_position_weight_proposed = round6(TOP_proposed_raw)`
   - `single_position_concentration.top_position_weight_delta = round6(TOP_proposed_raw - TOP_current_raw)`

When no proposed values are available, the implemented service sets
`TOP_proposed_raw = TOP_current_raw`; the emitted delta is therefore `0.0`.

Driver payloads use the same denominator and select the position row with the largest absolute
value. If multiple rows have the same absolute value, the current implementation selects the row
with the lexicographically largest `security_id` among tied values.

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
5. Compute current top-position weight from current values.
6. Compute proposed top-position weight from proposed values, or reuse current top-position weight
   when proposed values are empty.
7. Compute proposed-minus-current delta.
8. Build `top_position_current` and `top_position_proposed` driver payloads from the selected
   current/proposed rows.
9. Round each emitted weight and delta to six decimal places.

## Validation and Failure Behavior
- Empty current values produce `single_position_concentration.top_position_weight_current = 0.0`.
- Empty proposed values do not create an error; proposed top-position weight and driver fall back
  to current state.
- Missing, non-numeric, zero, and negative values are excluded from the value vector.
- A single valid position produces top-position weight `1.0`.
- Equal weights across `N` valid positions produce top-position weight `1 / N`.
- Issuer enrichment coverage does not change `single_position_concentration.top_position_*`;
  issuer coverage applies to `issuer_concentration`, not single-position concentration.
- The endpoint may still emit degraded calculation supportability for issuer coverage gaps, but
  top-position weight remains calculated from the available position values.

## Configuration Options
- No direct request option changes the top-position formula.
- Options that can change the source position universe:
  - `include_cash_positions`
  - `include_zero_quantity_positions`
  - `reporting_currency`
- Options that do not change the top-position formula:
  - `top_n`
  - `issuer_grouping_level`
  - `enrichment_policy`

## Outputs
- `single_position_concentration.top_position_weight_current`
- `single_position_concentration.top_position_weight_proposed`
- `single_position_concentration.top_position_weight_delta`
- `single_position_concentration.top_position_current`
- `single_position_concentration.top_position_proposed`

## Worked Example
Current values `[50, 30, 20]`; proposed values `[60, 25, 15]`.

| State | Values | Denominator | Weights | Selected Position | Top Position Weight |
|---|---|---:|---|---|---:|
| Current | `[50, 30, 20]` | `100` | `[0.50, 0.30, 0.20]` | first position | `0.50` |
| Proposed | `[60, 25, 15]` | `100` | `[0.60, 0.25, 0.15]` | first position | `0.60` |

Delta:

`single_position_concentration.top_position_weight_delta = 0.60 - 0.50 = 0.10`.

Output mapping:

- `single_position_concentration.top_position_weight_current = 0.50`
- `single_position_concentration.top_position_weight_proposed = 0.60`
- `single_position_concentration.top_position_weight_delta = 0.10`
- `single_position_concentration.top_position_current` identifies the current top position
- `single_position_concentration.top_position_proposed` identifies the proposed top position
