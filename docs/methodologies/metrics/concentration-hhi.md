# Concentration Methodology - Position HHI

## Metric
- metric_id: POSITION_HHI

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Current and proposed position values (market value preferred, quantity fallback).
- Top-N setting for related concentration fields.

## Upstream Data Sources
- Stateless: caller-provided current/projected positions.
- Stateful/simulation: lotus-core baseline and simulated snapshots.

## Unit Conventions
- Position inputs are non-negative portfolio amounts:
  - `market_value_base` when available
  - `quantity` as fallback when market value is unavailable
- Position weights are decimals in `[0, 1]`.
- HHI is reported on the conventional `0..10000` scale.

## Variable Dictionary
- `v_i`: position value for position `i`.
- `V = sum_i |v_i|`: absolute total exposure.
- `w_i = |v_i|/V`: normalized absolute position weight.
- `HHI = sum_i(w_i^2)*10000`: concentration index.
- `HHI_current`, `HHI_proposed`, `HHI_delta`: output trio.

## Methodology and Formulas
1. Compute absolute denominator `V = sum_i |v_i|` for each state.
2. Compute position weights `w_i = |v_i| / V`.
3. Compute `HHI = sum_i (w_i^2) * 10000` for current and proposed states.
4. Compute `HHI_delta = HHI_proposed - HHI_current`.

## Step-by-Step Computation
1. Extract numeric values from input rows.
2. Build current and proposed value vectors.
3. Normalize to absolute weights.
4. Compute HHI per state and delta.
5. Round to service precision and emit response.

## Validation and Failure Behavior
- If no valid values are available, HHI defaults to `0`.
- Non-numeric, missing, or non-positive values are ignored by the engine after contract parsing.
- HHI is bounded in `[0, 10000]` for non-negative exposure sets.

## Configuration Options
- No direct configuration option changes the HHI formula.
- Related endpoint options that change the input set:
  - `include_cash_positions`
  - `include_zero_quantity_positions`
  - `reporting_currency`

## Outputs
- `risk_proxy.hhi_current`
- `risk_proxy.hhi_proposed`
- `risk_proxy.hhi_delta`
- The concentration endpoint also exposes top-position fields in `single_position_concentration`, but those are separate metrics.

## Worked Example
Current values `[50, 30, 20]`; proposed values `[60, 25, 15]`.
| State | Values | Weights | Squared Weights | HHI |
|---|---|---|---:|
| Current | `[50,30,20]` | `[0.50,0.30,0.20]` | `[0.2500,0.0900,0.0400]` | `3800` |
| Proposed | `[60,25,15]` | `[0.60,0.25,0.15]` | `[0.3600,0.0625,0.0225]` | `4450` |
Delta: `4450 - 3800 = 650`.
Output mapping: `risk_proxy.hhi_current=3800`, `hhi_proposed=4450`, `hhi_delta=650`.
