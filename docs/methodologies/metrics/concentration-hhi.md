# Concentration Methodology - Position HHI

## Metric
- metric_id: POSITION_HHI

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Current and projected position values

## Upstream Data Sources
- Stateless: caller positions
- Stateful: lotus-core core-snapshot positions_baseline
- Simulation: lotus-core simulation session + changes + simulated snapshot

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- w_i = |v_i|/Σ|v|
- HHI = Σ(w_i^2)*10000

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: w_i = |v_i|/Σ|v|
4. Apply: HHI = Σ(w_i^2)*10000
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- include_cash_positions
- include_zero_quantity_positions
- top_n (not used directly in HHI)

## Outputs
- risk_proxy.hhi_current
- risk_proxy.hhi_proposed
- risk_proxy.hhi_delta

## Worked Example
Given:
- Values [50,30,20] => HHI=3800
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

