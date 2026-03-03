# Drawdown Methodology - Drawdown-at-Risk and CDaR

## Metric
- metric_id: DAR_CDAR

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Episode depth distribution.
- Tail confidence alpha.

## Upstream Data Sources
- Derived from drawdown episode extraction.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Variable Dictionary
- `d_i`: drawdown episode depth for episode `i` (decimal, non-positive).
- `D`: depth vector `[d_1, d_2, ..., d_n]`.
- `n`: number of drawdown episodes.
- `alpha`: confidence level from `analysis_options.cdar_alpha` (for example `0.95`).
- `q`: tail quantile level, `q = 1 - alpha`.
- `DAR_alpha`: drawdown-at-risk threshold at quantile `q`.
- `T`: tail set `{d_i | d_i <= DAR_alpha}`.
- `CDAR_alpha`: conditional drawdown-at-risk, mean depth over `T`.

## Methodology and Formulas
1. Build episode depth vector:
`D = [d_1, d_2, ..., d_n]`, with each `d_i <= 0`.
2. Set tail quantile level:
`q = 1 - alpha`.
3. Compute drawdown-at-risk threshold:
`DAR_alpha = quantile(D, q)` using linear interpolation.
4. Build worst-tail set:
`T = {d_i in D | d_i <= DAR_alpha}`.
5. Compute conditional drawdown-at-risk:
`CDAR_alpha = mean(T)` when `T` is non-empty.
6. If no episode depths are available, both DAR/CDaR are `null`.

## Step-by-Step Computation
1. Compute drawdown path and extract drawdown episodes.
2. Collect one depth value per episode into vector `D`.
3. If `D` is empty, emit `drawdown_at_risk_95 = null` and `conditional_drawdown_at_risk_95 = null`.
4. Compute `q = 1 - alpha`.
5. Compute quantile threshold `DAR_alpha` from `D` using linear interpolation.
6. Select tail subset `T` containing all depths at or below `DAR_alpha`.
7. Compute `CDAR_alpha = mean(T)`.
8. Return DAR and CDaR in summary payload.

## Validation and Failure Behavior
- `alpha` must be in `(0,1)` via request-contract validation.
- If no episodes exist in the period, both DAR and CDaR are `null`.
- If only one episode exists, DAR and CDaR are that episode depth.
- DAR and CDaR are expected to be `<= 0`; values closer to `0` indicate milder downside episodes.

## Configuration Options
- `analysis_options.cdar_alpha`

## Outputs
- `summary.drawdown_at_risk_95`
- `summary.conditional_drawdown_at_risk_95`

## Worked Example
Assume extracted episode depths (decimal):
`D = [-0.04, -0.07, -0.10, -0.02]`

Sort ascending for quantile computation:
`D_sorted = [-0.10, -0.07, -0.04, -0.02]`, `n = 4`

Set confidence:
- `alpha = 0.95`
- `q = 1 - alpha = 0.05`

Linear-quantile position:
- `h = (n - 1) * q = 3 * 0.05 = 0.15`
- Lower index `0`, upper index `1`
- Lower value `-0.10`, upper value `-0.07`

Interpolate DAR:
- `DAR_0.95 = -0.10 + 0.15 * (-0.07 - (-0.10))`
- `DAR_0.95 = -0.10 + 0.15 * 0.03 = -0.0955`

Tail set and CDaR:
- `T = {d_i | d_i <= -0.0955} = [-0.10]`
- `CDAR_0.95 = mean([-0.10]) = -0.10`

Output mapping:
- `summary.drawdown_at_risk_95 = -0.0955`
- `summary.conditional_drawdown_at_risk_95 = -0.10`

| Step | Value |
|---|---|
| Example DAR | `-0.0955` |
| Example CDaR | `-0.10` |
