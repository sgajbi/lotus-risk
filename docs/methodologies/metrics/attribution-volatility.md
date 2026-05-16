# Historical Attribution Methodology - Volatility Contribution

## Metric
- metric_id: VOLATILITY_ATTRIBUTION

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/historical-attribution
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns.
- Exposure history by grouping dimension.
- Annualization basis.

## Upstream Data Sources
- Stateless caller datasets or stateful integrated contracts.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when required: `r_decimal = r_pp / 100`.
- Output units are metric-specific (ratio, annualized pp, decimal drawdown, or HHI scale).

## Variable Dictionary
- `m_t = r_t/100`: metric return series (total risk).
- `w_{k,t}`: exposure weight for group `k` at date `t`.
- `g_{k,t} = w_{k,t}*m_t`: group pseudo-return series.
- `Total = std(m_t,ddof=1)*sqrt(AB)`.
- `CC_k = cov(g_k,m)/std(m)*sqrt(AB)`.
- `Residual = Total - sum_k(CC_k)`.

## Methodology and Formulas
1. `Total=std(m_t,ddof=1)*sqrt(annualization_basis)`.
2. `CC_k=cov(g_k,m)/std(m)*sqrt(annualization_basis)`.
3. `Residual=Total-sum(CC_k)`.

## Step-by-Step Computation
1. Resolve period and grouping.
2. Pivot exposure history into matrix.
3. Compute total volatility and group contributions.
4. Emit contributors, reconciled sum, and residual diagnostics.

## Validation and Failure Behavior
- Insufficient observations produce empty contributors and diagnostics.
- Weight-sum deviations add quality flags.
- Unsupported attribution combinations return quality flags.
- Any emitted attribution-set quality flag degrades
  `metadata.calculation_supportability` with reason `calculation_quality_issue`; downstream
  services must preserve the source-owned supportability posture instead of treating flagged
  attribution as fully ready.

## Configuration Options
- `attribution_options.grouping_dimensions`
- `attribution_options.metrics`
- `attribution_options.attribution_types`
- `attribution_options.annualization_basis`

## Outputs
- `attribution_sets[].total_value`
- `attribution_sets[].contributors[]`
- `attribution_sets[].reconciled_sum`
- `attribution_sets[].residual`

## Worked Example
Example total volatility `0.182` with groups A and B.
| Group | Component Contribution |
|---|---:|
| A | `0.110` |
| B | `0.070` |
Reconciled sum `0.180`; residual `0.002`.
Output mapping: values emitted in `contributors[]`, `reconciled_sum`, and `residual`.
