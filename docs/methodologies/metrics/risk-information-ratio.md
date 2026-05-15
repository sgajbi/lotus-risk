# Risk Metric Methodology - Information Ratio

## Metric
- metric_id: INFORMATION_RATIO

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return observations for the resolved period, with at least two aligned observations
  after period filtering and frequency resampling.
- Benchmark return observations for the same resolved period, with at least two aligned
  observations after filtering and resampling.
- Calculation frequency: `DAILY`, `WEEKLY`, or `MONTHLY`.
- Optional annualization-factor override.
- Optional log-return transform flag.

## Upstream Data Sources
- Stateless mode: caller-provided `returns` and `benchmark_returns`.
- Stateful mode: `lotus-performance` portfolio and benchmark return series fetched through the
  governed risk-calculate integration path.
- `lotus-risk` owns the information-ratio calculation after dated portfolio and benchmark return
  series are resolved. It does not source portfolio returns, benchmark returns, active-return
  assumptions, or information-ratio assumptions from Workbench, Gateway, or manage.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Frequency resampling compounds percentage-point returns and emits percentage-point period
  returns.
- If `options.use_log_returns=true`, both portfolio and benchmark returns are transformed with
  `r_log_pp = ln(1 + r_pp / 100) * 100` before alignment.
- Mean-return details are stored as decimal ratios:
  `details.portfolio_mean_return = mean(Rp_used_pp) / 100`,
  `details.benchmark_mean_return = mean(Rb_used_pp) / 100`, and
  `details.active_mean_return = mean(A_used_pp) / 100`.
- Tracking-error detail is stored as a decimal ratio:
  `details.tracking_error = std(A_used_pp, ddof=1) / 100`.
- Annualized active-return detail is stored as a decimal ratio:
  `details.annualized_active_return = details.active_mean_return * AF`.
- Annualized tracking-error detail is stored as a decimal ratio:
  `details.annualized_tracking_error = details.tracking_error * sqrt(AF)`.
- `metrics.INFORMATION_RATIO.value` is a dimensionless annualized ratio.

## Variable Dictionary
- `t`: aligned observation date after strict inner date alignment.
- `Rp_t_pp`: portfolio return on date `t`, in percentage points.
- `Rb_t_pp`: benchmark return on date `t`, in percentage points.
- `Rp_t_used_pp`: portfolio return used for information ratio after optional log transformation,
  in percentage points.
- `Rb_t_used_pp`: benchmark return used for information ratio after optional log transformation,
  in percentage points.
- `A_t_pp`: active return in percentage points, `A_t_pp = Rp_t_used_pp - Rb_t_used_pp`.
- `n_aligned`: number of aligned portfolio/benchmark observations.
- `mu_p_decimal`: mean portfolio return as a decimal ratio.
- `mu_b_decimal`: mean benchmark return as a decimal ratio.
- `mu_a_pp`: mean active return in percentage points.
- `mu_a_decimal`: mean active return as a decimal ratio.
- `sigma_a_pp`: sample active-return standard deviation with `ddof=1`, in percentage points.
- `sigma_a_decimal`: `sigma_a_pp / 100`.
- `AF`: annualization factor.
- `annualized_active_decimal`: `mu_a_decimal * AF`.
- `annualized_tracking_error_decimal`: `sigma_a_decimal * sqrt(AF)`.
- `IR`: dimensionless annualized information ratio.

## Methodology and Formulas
1. Resolve the requested period from `scope.as_of_date`, `portfolio_open_date`, and the period
   definition.
2. Filter portfolio and benchmark returns to the resolved period.
3. Resample both series when `options.frequency` is not `DAILY`:
   `r_period_pp = (product(1 + r_i_pp / 100) - 1) * 100`.
4. Apply the optional log-return transform to both series:
   - when `options.use_log_returns=false`, `Rp_t_used_pp = Rp_t_pp` and
     `Rb_t_used_pp = Rb_t_pp`;
   - when `options.use_log_returns=true`,
     `r_t_used_pp = ln(1 + r_t_pp / 100) * 100` for each series.
5. Strictly inner-align portfolio and benchmark returns by date.
6. Require at least two aligned observations.
7. Compute active returns:
   `A_t_pp = Rp_t_used_pp - Rb_t_used_pp`.
8. Compute active-return mean and sample standard deviation:
   - `mu_a_pp = mean(A_used_pp)`;
   - `sigma_a_pp = std(A_used_pp, ddof=1)`.
9. Require `sigma_a_pp` to be non-zero under `np.isclose`.
10. Resolve annualization factor:
    - `AF = options.annualization_factor` when supplied;
    - otherwise `AF = 252` for `DAILY`, `52` for `WEEKLY`, and `12` for `MONTHLY`.
11. Convert details to decimal ratios:
    - `mu_a_decimal = mu_a_pp / 100`;
    - `sigma_a_decimal = sigma_a_pp / 100`;
    - `annualized_active_decimal = mu_a_decimal * AF`;
    - `annualized_tracking_error_decimal = sigma_a_decimal * sqrt(AF)`.
12. Compute annualized information ratio:
    `IR = (mu_a_pp / sigma_a_pp) * sqrt(AF)`.

## Step-by-Step Computation
1. Build dated portfolio and benchmark return series and sort both by date.
2. Resolve each requested period.
3. Filter both return series to the period date range.
4. Apply weekly or monthly compounding to both series when requested.
5. Apply log-return transformation to both series when requested.
6. Inner-align both series by date.
7. Validate that at least two aligned observations remain.
8. Compute `details.portfolio_mean_return`, `details.benchmark_mean_return`, and
   `details.active_mean_return` as decimal ratios.
9. Compute `details.tracking_error` as decimal sample active-return standard deviation.
10. Compute `details.annualized_active_return` and `details.annualized_tracking_error` as decimal
    ratios.
11. Compute `metrics.INFORMATION_RATIO.value` as a dimensionless annualized ratio.
12. Preserve `details.aligned_observation_count` and `details.annualization_factor` for
    auditability.

## Validation and Failure Behavior
- Missing benchmark returns for `INFORMATION_RATIO` return `metrics.INFORMATION_RATIO.value = null`
  with `details.error = "Benchmark returns required for benchmark-dependent metric"`.
- Fewer than two aligned observations after period filtering, resampling, and optional
  transformation return `metrics.INFORMATION_RATIO.value = null` with
  `details.error = "Insufficient aligned observations"`.
- Zero or near-zero active-return standard deviation returns
  `metrics.INFORMATION_RATIO.value = null` with `details.error = "Tracking error is zero"`.
- Non-numeric return values are rejected by request-contract validation before engine math.
- No risk-free dependency is required for `INFORMATION_RATIO`.
- The denominator is `sigma_a_pp`; zero denominator is fail-closed and is not promoted as a valid
  ratio.

## Configuration Options
- `options.frequency`
- `options.annualization_factor`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.INFORMATION_RATIO.value`
- `results[period].metrics.INFORMATION_RATIO.details.aligned_observation_count`
- `results[period].metrics.INFORMATION_RATIO.details.annualization_factor`
- `results[period].metrics.INFORMATION_RATIO.details.portfolio_mean_return`
- `results[period].metrics.INFORMATION_RATIO.details.benchmark_mean_return`
- `results[period].metrics.INFORMATION_RATIO.details.active_mean_return`
- `results[period].metrics.INFORMATION_RATIO.details.tracking_error`
- `results[period].metrics.INFORMATION_RATIO.details.annualized_active_return`
- `results[period].metrics.INFORMATION_RATIO.details.annualized_tracking_error`
- `results[period].metrics.INFORMATION_RATIO.details.error`

## Worked Example
Assume no log transform (`options.use_log_returns=false`), daily frequency, default daily
annualization (`AF = 252`), and aligned return observations:

| Date | `Rp_t_used_pp` | `Rb_t_used_pp` | `A_t_pp` |
| --- | ---: | ---: | ---: |
| Day 1 | `1.00` | `0.80` | `0.20` |
| Day 2 | `-0.50` | `-0.60` | `0.10` |
| Day 3 | `0.20` | `0.30` | `-0.10` |
| Day 4 | `0.00` | `0.00` | `0.00` |

Intermediate calculations:

| Step | Value |
| --- | ---: |
| Mean portfolio return, pp | `0.1750000000` |
| Mean benchmark return, pp | `0.1250000000` |
| Mean active return, pp | `0.0500000000` |
| `details.portfolio_mean_return` | `0.0017500000` |
| `details.benchmark_mean_return` | `0.0012500000` |
| `details.active_mean_return` | `0.0005000000` |
| Active squared deviations sum | `0.0500000000` |
| Sample active variance, pp (`ddof=1`) | `0.0166666667` |
| `sigma_a_pp` | `0.1290994449` |
| `details.tracking_error = sigma_a_pp / 100` | `0.0012909944` |
| Annualization multiplier | `sqrt(252) = 15.8745078664` |
| `details.annualized_active_return` | `0.1260000000` |
| `details.annualized_tracking_error` | `0.0204939015` |
| `IR = (mu_a_pp / sigma_a_pp) * sqrt(AF)` | `6.1481704596` |

Output mapping:

- `results[period].metrics.INFORMATION_RATIO.value = 6.1481704596`
- `results[period].metrics.INFORMATION_RATIO.details.aligned_observation_count = 4`
- `results[period].metrics.INFORMATION_RATIO.details.annualization_factor = 252`
- `results[period].metrics.INFORMATION_RATIO.details.portfolio_mean_return = 0.0017500000`
- `results[period].metrics.INFORMATION_RATIO.details.benchmark_mean_return = 0.0012500000`
- `results[period].metrics.INFORMATION_RATIO.details.active_mean_return = 0.0005000000`
- `results[period].metrics.INFORMATION_RATIO.details.tracking_error = 0.0012909944`
- `results[period].metrics.INFORMATION_RATIO.details.annualized_active_return = 0.1260000000`
- `results[period].metrics.INFORMATION_RATIO.details.annualized_tracking_error = 0.0204939015`
