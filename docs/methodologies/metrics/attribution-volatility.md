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

## Methodology and Formulas
- metric_series = portfolio returns (decimal)
- group_matrix = exposure_weight * metric_series
- total_value = std(metric_series)*sqrt(annualization_basis)
- component_i = cov(group_i,metric_series)/std(metric_series)*sqrt(annualization_basis)
- marginal_i = component_i/avg_weight_i
- percent_i = component_i/total_value

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
- Components [0.08,0.04] reconcile to total 0.12 => percents 66.7%/33.3%
