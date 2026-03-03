# Historical Attribution Methodology - Volatility Attribution

## Metric
- metric_id: ATTRIBUTION_VOLATILITY

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/historical-attribution
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Portfolio exposure history by grouping dimension
- Periods and annualization basis

## Upstream Data Sources
- Stateless: caller returns + exposure_history
- Stateful: lotus-performance returns + lotus-core position-timeseries + enrichment

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- metric_series = portfolio returns (decimal)
- group_matrix = exposure_weight * metric_series
- total_value = std(metric_series)*sqrt(annualization_basis)
- component_i = cov(group_i,metric_series)/std(metric_series)*sqrt(annualization_basis)
- marginal_i = component_i/avg_weight_i
- percent_i = component_i/total_value

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: metric_series = portfolio returns (decimal)
4. Apply: group_matrix = exposure_weight * metric_series
5. Apply: total_value = std(metric_series)*sqrt(annualization_basis)
6. Apply: component_i = cov(group_i,metric_series)/std(metric_series)*sqrt(annualization_basis)
7. Apply: marginal_i = component_i/avg_weight_i
8. Apply: percent_i = component_i/total_value
9. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- attribution_options.attribution_types includes TOTAL_RISK
- metrics includes VOLATILITY
- grouping_dimensions
- annualization_basis
- covariance_method=EMPIRICAL

## Outputs
- attribution_sets[].total_value
- reconciled_sum
- residual
- contributors[].marginal_contribution/component_contribution/percent_contribution

## Worked Example
Given:
- Components [0.08,0.04] reconcile to total 0.12 => percents 66.7%/33.3%
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

