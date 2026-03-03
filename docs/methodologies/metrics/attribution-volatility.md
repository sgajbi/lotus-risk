# Historical Attribution Methodology - Volatility Contribution

## Metric
- metric_id: VOLATILITY_ATTRIBUTION

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/historical-attribution
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns.
- Exposure history by grouping.
- Annualization basis.

## Upstream Data Sources
- Stateless caller datasets.
- Stateful integrated data contracts.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. `m_t=r_t/100`.
2. `g_{k,t}=w_{k,t}*m_t`.
3. Total `sigma=std(m_t)*sqrt(annualization_basis)`.
4. Contribution `CC_k = cov(g_k,m)/std(m)*sqrt(annualization_basis)`.

## Step-by-Step Computation
1. Pivot exposure history into date x group matrix.
2. Build group pseudo-return matrix.
3. Compute per-group component contributions.
4. Reconcile sum and residual against total volatility.

## Configuration Options
- `attribution_options.grouping_dimensions`
- `attribution_options.metrics`
- `attribution_options.annualization_basis`

## Outputs
- `attribution_sets[].contributors[]`
- `total_value`
- `reconciled_sum`
- `residual`

## Worked Example
- Compute metric series `m_t = r_t/100` over aligned dates.
- For each group k, build pseudo series `g_{k,t}=w_{k,t}*m_t`.
- Compute each component: `CC_k=cov(g_k,m)/std(m)*sqrt(annualization_basis)`.
- Example total volatility `0.182`, components `0.110` and `0.070`.
- Reconciled sum `0.180`, residual `0.002` reported explicitly.
