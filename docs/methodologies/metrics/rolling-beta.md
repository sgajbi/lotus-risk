# Rolling Metric Methodology - Rolling Beta

## Metric
- metric_id: ROLLING_BETA

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio and benchmark returns.
- Window lengths.

## Upstream Data Sources
- Stateless caller.
- Stateful lotus-performance.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Convert both portfolio and benchmark return series from pp to decimal:
`r_decimal = r_pp / 100`.
2. For each window end date `t` and window size `W`, define trailing slices:
`Rp_t(W)` and `Rb_t(W)`.
3. Compute rolling sample covariance:
`cov_t = cov(Rp_t(W), Rb_t(W), ddof=1)`.
4. Compute rolling sample benchmark variance:
`var_t = var(Rb_t(W), ddof=1)`.
5. Compute rolling beta:
`beta_t(W) = cov_t / var_t`.
6. If `var_t == 0`, output is null for that point and a quality flag is emitted.

## Step-by-Step Computation
1. Align portfolio and benchmark returns by date (inner join).
2. Build rolling covariance and rolling variance vectors for each requested window length.
3. Divide covariance by variance point-by-point to obtain rolling beta.
4. Replace infinite values with null and attach `benchmark_variance_zero` quality flags.
5. Compute window-level summary statistics (`latest`, `average`, percentiles) from non-null points.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.min_observations_policy`

## Outputs
- `window_results[].metric_summaries.ROLLING_BETA`
- `quality_flags`

## Worked Example
- Window data: benchmark decimal `[0.01,-0.02,0.015]` and portfolio `[0.015,-0.03,0.0225]`.
- Portfolio is exactly 1.5x benchmark at each point.
- Rolling covariance equals `1.5 * rolling_var(benchmark)`.
- Rolling beta for that window = `1.5`.
- Summary fields aggregate all rolling-beta points over the period.
