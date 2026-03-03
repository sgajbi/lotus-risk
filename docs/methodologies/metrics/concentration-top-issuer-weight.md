# Concentration Methodology - Top Issuer Weight

## Metric
- metric_id: TOP_ISSUER_WEIGHT

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Issuer aggregated totals

## Upstream Data Sources
- Same as ISSUER_HHI

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- issuer_weight_j = |issuer_total_j|/Σ|issuer_total|
- Top issuer = max_j(issuer_weight_j)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: issuer_weight_j = |issuer_total_j|/Σ|issuer_total|
4. Apply: Top issuer = max_j(issuer_weight_j)
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- issuer_grouping_level
- enrichment_policy

## Outputs
- issuer_concentration.top_issuer_weight_current/proposed/delta

## Worked Example
Given:
- Issuer totals [70,30] => top issuer weight=0.7
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

