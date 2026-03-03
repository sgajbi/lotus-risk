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

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- Aggregate position values by issuer bucket
- Apply HHI formula to issuer totals

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: Aggregate position values by issuer bucket
4. Apply: Apply HHI formula to issuer totals
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- issuer_grouping_level
- enrichment_policy

## Outputs
- issuer_concentration.hhi_current/proposed/delta
- issuer_concentration.coverage_status + counters

## Worked Example
Given:
- Issuer totals [70,30] => issuer HHI=5800
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

