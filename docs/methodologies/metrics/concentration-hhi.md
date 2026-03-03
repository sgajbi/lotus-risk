# Concentration Methodology - Position HHI

## Metric
- metric_id: POSITION_HHI

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Current and proposed position values.
- Top-N option for ancillary fields.

## Upstream Data Sources
- Stateless caller payload.
- Stateful/simulation snapshots from lotus-core.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Build absolute exposure denominator for each state: `V = sum_i |v_i|`.
2. Compute position weights: `w_i = |v_i| / V`.
3. Compute concentration score: `HHI = sum_i(w_i^2) * 10000`.
4. Compute transition delta: `HHI_delta = HHI_proposed - HHI_current`.

## Step-by-Step Computation
1. Extract usable numeric value per position (`market_value_base`; fallback `quantity`).
2. Build baseline and proposed absolute-value vectors.
3. Normalize each vector into weights using absolute total denominator.
4. Square-and-sum weights and scale by 10,000 for current and proposed states.
5. Emit rounded current/proposed/delta values in risk proxy payload.

## Configuration Options
- `concentration_options.top_n`

## Outputs
- `risk_proxy.hhi_current`
- `risk_proxy.hhi_proposed`
- `risk_proxy.hhi_delta`

## Worked Example
- Current values `[50, 30, 20]`, absolute total `100`.
- Current weights `[0.50, 0.30, 0.20]`.
- Current HHI `=(0.50^2+0.30^2+0.20^2)*10000 = 3800`.
- Proposed values `[60, 25, 15]` -> weights `[0.60,0.25,0.15]`.
- Proposed HHI `4450`; delta `+650`.