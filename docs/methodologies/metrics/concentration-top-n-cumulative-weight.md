# Concentration Methodology - Top-N Cumulative Weight

## Metric
- metric_id: TOP_N_CUMULATIVE_WEIGHT

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Position values
- top_n

## Upstream Data Sources
- Same data sources as POSITION_HHI

## Methodology and Formulas
- Compute weights
- Sort descending
- Sum first N

## Configuration Options
- top_n

## Outputs
- single_position_concentration.top_n_cumulative_weight_current/proposed/delta
- single_position_concentration.top_n

## Worked Example
- Weights [0.5,0.3,0.2], top_n=2 => 0.8
