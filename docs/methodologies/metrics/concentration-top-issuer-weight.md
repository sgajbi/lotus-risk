# Concentration Methodology - Top Issuer Weight

## Metric
- metric_id: TOP_ISSUER_WEIGHT

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Issuer-bucketed values for current/proposed states.

## Upstream Data Sources
- Derived from issuer mapping and issuer aggregation path.

## Unit Conventions
- Position inputs are non-negative portfolio amounts:
  - `market_value_base` when available
  - `quantity` as fallback when market value is unavailable
- Issuer weights are decimals in `[0, 1]`.

## Variable Dictionary
- `issuer_value_k`: aggregate value for issuer `k`.
- `W_issuer = sum_k |issuer_value_k|`.
- `w_k = |issuer_value_k|/W_issuer`.
- `TOP_ISSUER = max_k(w_k)`.
- `TOP_ISSUER_delta = TOP_ISSUER_proposed - TOP_ISSUER_current`.

## Methodology and Formulas
1. Aggregate values by issuer.
2. Normalize to issuer weights.
3. Take max issuer weight for each state.
4. Compute delta.

## Step-by-Step Computation
1. Resolve issuer buckets.
2. Compute issuer weights.
3. Select max weight current/proposed.
4. Emit delta and coverage context.

## Validation and Failure Behavior
- Empty issuer buckets yield top issuer weight `0`.
- Coverage flags indicate mapping completeness.

## Configuration Options
- `issuer_grouping_level`
- `enrichment_policy`
- Stateful and simulation portfolio-state options can change the covered universe:
  - `include_cash_positions`
  - `include_zero_quantity_positions`

## Outputs
- `issuer_concentration.top_issuer_weight_current`
- `issuer_concentration.top_issuer_weight_proposed`
- `issuer_concentration.top_issuer_weight_delta`
- `issuer_concentration.top_issuer_current`
- `issuer_concentration.top_issuer_proposed`

## Worked Example
Issuer weights current `[0.80,0.20]`, proposed `[0.70,0.30]`.
| State | Issuer Weights | Selected Top Issuer | Top Issuer Weight |
|---|---|---|---:|
| Current | `[0.80,0.20]` | issuer X | `0.80` |
| Proposed | `[0.70,0.30]` | issuer X | `0.70` |
Delta: `-0.10`.
Output mapping:
- `issuer_concentration.top_issuer_weight_current=0.80`
- `issuer_concentration.top_issuer_weight_proposed=0.70`
- `issuer_concentration.top_issuer_weight_delta=-0.10`
- `issuer_concentration.top_issuer_current` identifies the current top issuer
