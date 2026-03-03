# Historical Attribution Methodology - Tracking Error Contribution

## Metric
- metric_id: TRACKING_ERROR_ATTRIBUTION

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/historical-attribution
- supported_modes: stateless, stateful

## Inputs
- Portfolio and benchmark returns.
- Portfolio and benchmark exposure history.

## Upstream Data Sources
- Stateless caller datasets.
- Stateful integrated contracts (including benchmark exposure history).

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. `a_t=(Rp_t-Rb_t)/100`.
2. `aw_{k,t}=w_p_{k,t}-w_b_{k,t}`.
3. `g_{k,t}=aw_{k,t}*a_t`.
4. `TE=std(a_t)*sqrt(annualization_basis)`.
5. `CC_k=cov(g_k,a)/std(a)*sqrt(annualization_basis)`.

## Step-by-Step Computation
1. Align return and exposure series.
2. Build active return and active weight matrices.
3. Compute component contributions by group.
4. Reconcile against total tracking error.

## Configuration Options
- `attribution_options.attribution_types`
- `attribution_options.metrics`
- `attribution_options.annualization_basis`

## Outputs
- ACTIVE_RISK / TRACKING_ERROR attribution set with contributors and residual.

## Worked Example
- Compute active return `a_t=(Rp_t-Rb_t)/100` and active weights `aw_{k,t}`.
- Build group pseudo-active series `g_{k,t}=aw_{k,t}*a_t`.
- Component contribution: `CC_k=cov(g_k,a)/std(a)*sqrt(annualization_basis)`.
- Example TE total `0.045`, contributors `0.030` and `0.013`.
- Reconciled sum `0.043`, residual `0.002`.
