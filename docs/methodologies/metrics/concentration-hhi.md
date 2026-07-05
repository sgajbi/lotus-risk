# Concentration Methodology - Position HHI

## Metric
- metric_id: POSITION_HHI
- source_product: ConcentrationAnalyticsReport:v1
- methodology_version: concentration.position_hhi.v1

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation
- output_family: `risk_proxy`

## Inputs
- Current position rows.
- Proposed position rows when the caller supplies or source state resolves a projected state.
- Position identifiers and display names are carried into driver payloads, but `POSITION_HHI`
  uses only numeric position values.
- `top_n` is accepted by the endpoint for related top-N concentration fields but does not change
  the `POSITION_HHI` formula.

## Upstream Data Sources
- Stateless mode uses caller-provided `stateless_input.current_positions` and
  `stateless_input.projected_positions`.
- Stateful mode requests a lotus-core baseline snapshot and uses `positions_baseline` for both
  current and proposed states.
- Simulation mode creates or reuses a lotus-core simulation session, applies requested changes,
  requests a simulation snapshot, and uses baseline positions as current state and projected
  positions as proposed state.
- There is no lotus-performance dependency for position HHI.

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
- Position weights are decimal ratios in `[0, 1]`.
- `risk_proxy.hhi_*` values are emitted on the conventional Herfindahl-Hirschman `0..10000`
  scale and rounded to six decimal places by the service response.

## Variable Dictionary
- `C`: current extracted positive numeric position values.
- `P`: proposed extracted positive numeric position values.
- `x_i`: one extracted positive current value in `C`.
- `y_i`: one extracted positive proposed value in `P`.
- `V_C = sum_i(abs(x_i))`: current absolute exposure denominator.
- `V_P = sum_i(abs(y_i))`: proposed absolute exposure denominator.
- `w_i_current = abs(x_i) / V_C` when `V_C > 0`.
- `w_i_proposed = abs(y_i) / V_P` when `V_P > 0`.
- `HHI_current_raw = sum_i(w_i_current^2) * 10000`.
- `HHI_proposed_raw = sum_i(w_i_proposed^2) * 10000`.
- `HHI_delta_raw = HHI_proposed_raw - HHI_current_raw`.
- `round6(z)`: Python `round(z, 6)` used by the service response.

## Methodology and Formulas
For each state:

1. Extract one positive numeric value per usable position row according to the mode-specific
   field precedence.
2. Compute the denominator:
   `V = sum(abs(v_i))`.
3. If `V <= 0`, set the state HHI to `0.0`.
4. Otherwise compute normalized weights:
   `w_i = abs(v_i) / V`.
5. Compute the raw concentration index:
   `HHI_raw = sum(w_i^2) * 10000`.
6. Emit:
   - `risk_proxy.hhi_current = round6(HHI_current_raw)`
   - `risk_proxy.hhi_proposed = round6(HHI_proposed_raw)`
   - `risk_proxy.hhi_delta = round6(HHI_proposed_raw - HHI_current_raw)`

When no proposed values are available in stateless or stateful mode, the implemented service sets
`HHI_proposed_raw = HHI_current_raw`; the emitted delta is therefore `0.0`. Simulation mode is
source-owned by lotus-core: missing or invalid `positions_projected` is an upstream invalid
response, while an explicit empty `positions_projected: []` is treated as an empty proposed book
with `HHI_proposed_raw = 0.0`.

## Step-by-Step Computation
1. Resolve request mode.
2. Build current position entries:
   - stateless: caller current positions,
   - stateful: lotus-core baseline positions,
   - simulation: lotus-core baseline positions.
3. Build proposed position entries:
   - stateless: caller projected positions,
   - stateful: same baseline positions as current,
   - simulation: required lotus-core projected positions; an explicit empty list remains empty.
4. For each row, parse the preferred value field, fall back to the secondary value field, and keep
   only positive numeric values.
5. Compute current HHI from current values.
6. Compute proposed HHI from proposed values; reuse current HHI only for modes that intentionally
   use current state when proposed values are empty.
7. Compute proposed-minus-current delta.
8. Round each emitted HHI and delta to six decimal places.

## Validation and Failure Behavior
- Empty current values produce `risk_proxy.hhi_current = 0.0`.
- Empty stateless/stateful proposed values fall back to current HHI. Empty simulation projected
  positions produce proposed HHI `0.0`; missing or invalid simulation projected sections return
  `UPSTREAM_INVALID_RESPONSE`.
- Missing, non-numeric, zero, and negative values are excluded from the value vector.
- A single valid position produces HHI `10000.0`.
- Equal weights across `N` valid positions produce `10000 / N`.
- HHI is bounded in `[0, 10000]` for the implemented positive-value extraction path.
- Issuer enrichment coverage does not change `risk_proxy.hhi_*`; issuer coverage applies to
  `issuer_concentration`, not position HHI.
- The endpoint may still emit degraded calculation supportability for issuer coverage gaps, but
  position HHI remains calculated from the available position values.

## Configuration Options
- No direct request option changes the HHI formula.
- Options that can change the source position universe:
  - `include_cash_positions`
  - `include_zero_quantity_positions`
  - `reporting_currency`
- Options that do not change the position-HHI formula:
  - `top_n`
  - `issuer_grouping_level`
  - `enrichment_policy`

## Outputs
- `risk_proxy.hhi_current`
- `risk_proxy.hhi_proposed`
- `risk_proxy.hhi_delta`
- The concentration endpoint also exposes top-position and issuer-concentration fields, but those
  are separate metrics and do not alter `POSITION_HHI`.

## Worked Example
Current values `[50, 30, 20]`; proposed values `[60, 25, 15]`.

| State | Values | Denominator | Weights | Squared Weights | HHI |
|---|---|---:|---|---|---:|
| Current | `[50, 30, 20]` | `100` | `[0.50, 0.30, 0.20]` | `[0.2500, 0.0900, 0.0400]` | `3800.0` |
| Proposed | `[60, 25, 15]` | `100` | `[0.60, 0.25, 0.15]` | `[0.3600, 0.0625, 0.0225]` | `4450.0` |

Delta:

`risk_proxy.hhi_delta = 4450.0 - 3800.0 = 650.0`.

Output mapping:

- `risk_proxy.hhi_current = 3800.0`
- `risk_proxy.hhi_proposed = 4450.0`
- `risk_proxy.hhi_delta = 650.0`
