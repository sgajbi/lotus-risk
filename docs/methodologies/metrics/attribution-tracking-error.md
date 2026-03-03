# Historical Attribution Methodology - Tracking Error Attribution

## Metric
- metric_id: ATTRIBUTION_TRACKING_ERROR

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/historical-attribution
- supported_modes: stateless, stateful (partial)

## Inputs
- Portfolio returns
- Benchmark returns
- Portfolio and benchmark exposure histories

## Upstream Data Sources
- Stateless: caller supplies all required series
- Stateful: pending lotus-core benchmark exposure-history contract

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- active_return_t = Rp_t - Rb_t
- active_weight_{g,t} = w_p,{g,t} - w_b,{g,t}
- group_matrix = active_weight * active_return
- total_value = std(active_return)*sqrt(annualization_basis)
- covariance-based component decomposition as in volatility attribution

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: active_return_t = Rp_t - Rb_t
4. Apply: active_weight_{g,t} = w_p,{g,t} - w_b,{g,t}
5. Apply: group_matrix = active_weight * active_return
6. Apply: total_value = std(active_return)*sqrt(annualization_basis)
7. Apply: covariance-based component decomposition as in volatility attribution
8. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- attribution_options.attribution_types includes ACTIVE_RISK
- metrics includes TRACKING_ERROR
- grouping_dimensions
- annualization_basis

## Outputs
- attribution_sets for ACTIVE_RISK/TRACKING_ERROR
- contributors and reconciliation fields

## Worked Example
Given:
- Active return and active-weight series produce contributor components that reconcile to total tracking error
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

