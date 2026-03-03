# Concentration Methodology - Top Position Weight

## Metric
- metric_id: TOP_POSITION_WEIGHT

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Position values by state

## Upstream Data Sources
- Same data sources as POSITION_HHI

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- w_i = |v_i|/Σ|v|
- Top position = max_i(w_i)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: w_i = |v_i|/Σ|v|
4. Apply: Top position = max_i(w_i)
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- none beyond value selection rules

## Outputs
- single_position_concentration.top_position_weight_current/proposed/delta

## Worked Example
Given:
- Values [50,30,20] => top position weight=0.5
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

