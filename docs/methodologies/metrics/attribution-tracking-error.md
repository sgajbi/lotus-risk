# Historical Attribution Methodology - Tracking Error Contribution

## Metric
- metric_id: TRACKING_ERROR_ATTRIBUTION

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/historical-attribution
- supported_modes: stateless, stateful

## Inputs
- Portfolio and benchmark returns.
- Portfolio and benchmark exposure histories.
- Annualization basis.

## Upstream Data Sources
- Stateless caller datasets or stateful integrated contracts.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when required: `r_decimal = r_pp / 100`.
- Output units are metric-specific (ratio, annualized pp, decimal drawdown, or HHI scale).

## Variable Dictionary
- `a_t = (Rp_t - Rb_t)/100`: active return series.
- `w^P_{k,t}`, `w^B_{k,t}`: portfolio/benchmark exposure weights.
- `aw_{k,t} = w^P_{k,t} - w^B_{k,t}`: active weight.
- `g_{k,t} = aw_{k,t}*a_t`: group pseudo-active series.
- `TE_total = std(a_t,ddof=1)*sqrt(AB)`.
- `CC_k = cov(g_k,a)/std(a)*sqrt(AB)`.
- `Residual = TE_total - sum_k(CC_k)`.

## Methodology and Formulas
1. `TE_total=std(a_t,ddof=1)*sqrt(annualization_basis)`.
2. `CC_k=cov(g_k,a)/std(a)*sqrt(annualization_basis)`.
3. `Residual=TE_total-sum(CC_k)`.

## Step-by-Step Computation
1. Resolve and align return and exposure series.
2. Build active return and active weight matrices.
3. Compute total tracking error and component contributions.
4. Emit diagnostics and quality flags.

## Validation and Failure Behavior
- Missing benchmark exposure history blocks active-risk attribution.
- Alignment-empty joins emit quality flags with no contributors.
- Near-zero denominators result in diagnostic/unsupported flags.

## Configuration Options
- `attribution_options.grouping_dimensions`
- `attribution_options.attribution_types`
- `attribution_options.metrics`
- `attribution_options.annualization_basis`

## Outputs
- `attribution_sets[].total_value`
- `attribution_sets[].contributors[]`
- `attribution_sets[].reconciled_sum`
- `attribution_sets[].residual`
- `attribution_sets[].quality_flags`

## Worked Example
Example TE total `0.045` with groups A and B.
| Group | Component Contribution |
|---|---:|
| A | `0.030` |
| B | `0.013` |
Reconciled sum `0.043`; residual `0.002`.
Output mapping: components in `contributors[]`, diagnostics in `reconciled_sum` and `residual`.