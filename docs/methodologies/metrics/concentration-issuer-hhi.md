# Concentration Methodology - Issuer HHI

## Metric
- metric_id: ISSUER_HHI

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Position values
- Security->issuer mapping

## Upstream Data Sources
- Caller issuer mappings and/or lotus-core enrichment-bulk according to enrichment_policy

## Methodology and Formulas
- Aggregate position values by issuer bucket
- Apply HHI formula to issuer totals

## Configuration Options
- issuer_grouping_level
- enrichment_policy

## Outputs
- issuer_concentration.hhi_current/proposed/delta
- issuer_concentration.coverage_status + counters

## Worked Example
- Issuer totals [70,30] => issuer HHI=5800
