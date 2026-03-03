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

## Methodology and Formulas
1. Extract episode depth vector from drawdown episodes:
`D = [d_1, d_2, ..., d_n]`, where each `d_i <= 0`.
2. Compute tail probability level:
`q = 1 - alpha`.
3. Drawdown-at-Risk:
`DAR_alpha = quantile(D, q)` (engine uses linear interpolation).
4. Tail set for conditional measure:
`T = {d_i in D | d_i <= DAR_alpha}`.
5. Conditional Drawdown-at-Risk:
`CDAR_alpha = mean(T)` when `T` is non-empty.

## Step-by-Step Computation
1. Build drawdown episodes and collect each episode depth.
2. Sort/quantile the depth vector at tail level `1-alpha`.
3. Identify episodes in the worst tail at or below DAR threshold.
4. Compute average of worst-tail depths for CDaR.
5. Return both DAR and CDaR in summary response fields.

## Configuration Options
- `analysis_options.cdar_alpha`

## Outputs
- `summary.drawdown_at_risk_95`
- `summary.conditional_drawdown_at_risk_95`

## Worked Example
- Episode depths example `[-0.04,-0.07,-0.10,-0.02]`.
- For alpha `0.95`, tail quantile level is `1-alpha = 0.05`.
- DAR is near lower-tail threshold, approximately `-0.095` to `-0.10` with this sample.
- Worst-tail set is `[-0.10]` (or includes close values by interpolation rule).
- CDaR is mean of worst-tail set, approximately `-0.10`.
