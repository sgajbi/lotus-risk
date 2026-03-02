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

## Methodology and Formulas
- w_i = |v_i|/Σ|v|
- Top position = max_i(w_i)

## Configuration Options
- none beyond value selection rules

## Outputs
- single_position_concentration.top_position_weight_current/proposed/delta

## Worked Example
- Values [50,30,20] => top position weight=0.5
