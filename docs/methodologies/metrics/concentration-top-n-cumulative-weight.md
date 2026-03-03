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

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- Compute weights
- Sort descending
- Sum first N

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: Compute weights
4. Apply: Sort descending
5. Apply: Sum first N
6. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- top_n

## Outputs
- single_position_concentration.top_n_cumulative_weight_current/proposed/delta
- single_position_concentration.top_n

## Worked Example
Given:
- Weights [0.5,0.3,0.2], top_n=2 => 0.8
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

