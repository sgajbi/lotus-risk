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

## Methodology and Formulas
- issuer_weight_j = |issuer_total_j|/Σ|issuer_total|
- Top issuer = max_j(issuer_weight_j)

## Configuration Options
- issuer_grouping_level
- enrichment_policy

## Outputs
- issuer_concentration.top_issuer_weight_current/proposed/delta

## Worked Example
- Issuer totals [70,30] => top issuer weight=0.7
