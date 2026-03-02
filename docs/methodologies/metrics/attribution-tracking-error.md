# Historical Attribution Methodology - Tracking Error Attribution

## Metric
- metric_id: ATTRIBUTION_TRACKING_ERROR

## Implementation Status
- Current state:
  - stateless: implemented
  - stateful: partially implemented
- Stateful dependency gap:
  - benchmark exposure history contract is required from `lotus-core` to compute active weights by grouping dimension.
  - expected upstream capability: benchmark exposure timeseries aligned to portfolio exposure timeseries window/dimension semantics.

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

## Methodology and Formulas
- active_return_t = Rp_t - Rb_t
- active_weight_{g,t} = w_p,{g,t} - w_b,{g,t}
- group_matrix = active_weight * active_return
- total_value = std(active_return)*sqrt(annualization_basis)
- covariance-based component decomposition as in volatility attribution

## Configuration Options
- attribution_options.attribution_types includes ACTIVE_RISK
- metrics includes TRACKING_ERROR
- grouping_dimensions
- annualization_basis

## Outputs
- attribution_sets for ACTIVE_RISK/TRACKING_ERROR
- contributors and reconciliation fields

## Worked Example
- Active return and active-weight series produce contributor components that reconcile to total tracking error
