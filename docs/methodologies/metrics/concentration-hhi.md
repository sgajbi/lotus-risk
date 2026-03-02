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

## Methodology and Formulas
- w_i = |v_i|/Σ|v|
- HHI = Σ(w_i^2)*10000

## Configuration Options
- include_cash_positions
- include_zero_quantity_positions
- top_n (not used directly in HHI)

## Outputs
- risk_proxy.hhi_current
- risk_proxy.hhi_proposed
- risk_proxy.hhi_delta

## Worked Example
- Values [50,30,20] => HHI=3800
