# Risk Metric Methodology - Tracking Error

## Metric
- metric_id: TRACKING_ERROR

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
- `lotus-risk` owns the tracking-error calculation after dated portfolio and benchmark return
  series are resolved. It does not source portfolio returns, benchmark returns, or tracking-error
  assumptions from Workbench, Gateway, or manage.

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
- Active-volatility detail is stored as a decimal ratio:
  `details.active_volatility = std(A_used_pp, ddof=1) / 100`.
- Annualized tracking-error detail is stored as a decimal ratio:
  `details.annualized_tracking_error = details.active_volatility * sqrt(AF)`.
- `metrics.TRACKING_ERROR.value` is an annualized percentage-point output:
  `2.7495` means `2.7495%`.

## Variable Dictionary
- `t`: aligned observation date after strict inner date alignment.
- `Rp_t_pp`: portfolio return on date `t`, in percentage points.
- `Rb_t_pp`: benchmark return on date `t`, in percentage points.
- `Rp_t_used_pp`: portfolio return used for tracking error after optional log transformation, in
  percentage points.
- `Rb_t_used_pp`: benchmark return used for tracking error after optional log transformation, in
  percentage points.
- `A_t_pp`: active return in percentage points, `A_t_pp = Rp_t_used_pp - Rb_t_used_pp`.
- `n_aligned`: number of aligned portfolio/benchmark observations.
- `mu_p_decimal`: mean portfolio return as a decimal ratio.
- `mu_b_decimal`: mean benchmark return as a decimal ratio.
- `mu_a_decimal`: mean active return as a decimal ratio.
- `sigma_a_pp`: sample active-return standard deviation with `ddof=1`, in percentage points.
- `sigma_a_decimal`: `sigma_a_pp / 100`.
- `AF`: annualization factor.
- `TE_pp`: annualized tracking-error output in percentage points.
- `TE_decimal`: annualized tracking-error detail as a decimal ratio.

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
8. Compute sample active-return standard deviation:
   `sigma_a_pp = std(A_used_pp, ddof=1)`.
9. Resolve annualization factor:
    - `AF = options.annualization_factor` when supplied;
    - otherwise `AF = 252` for `DAILY`, `52` for `WEEKLY`, and `12` for `MONTHLY`.
10. Convert details to decimal ratios:
    - `sigma_a_decimal = sigma_a_pp / 100`;
    - `TE_decimal = sigma_a_decimal * sqrt(AF)`.
11. Annualize and map the response value:
    `TE_pp = sigma_a_pp * sqrt(AF)`.

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
9. Compute `details.active_volatility` as decimal sample active-return standard deviation.
10. Compute `details.annualized_tracking_error` as decimal annualized active-return volatility.
11. Compute `metrics.TRACKING_ERROR.value` as annualized percentage points.
12. Preserve `details.aligned_observation_count` and `details.annualization_factor` for
    auditability.

## Validation and Failure Behavior
- Missing benchmark returns for `TRACKING_ERROR` return `metrics.TRACKING_ERROR.value = null` with
  `details.error = "Benchmark returns required for benchmark-dependent metric"`.
- Fewer than two aligned observations after period filtering, resampling, and optional
  transformation return `metrics.TRACKING_ERROR.value = null` with
  `details.error = "Insufficient aligned observations"`.
- When `options.use_log_returns=true`, any compounded portfolio or benchmark return less than or
  equal to `-100%` returns `metrics.TRACKING_ERROR.value = null` with
  `details.error = "Log returns are undefined for returns less than or equal to -100%"`.
- Constant active returns are valid and produce `0.0`.
- Non-numeric return values are rejected by request-contract validation before engine math.
- No risk-free dependency is required for `TRACKING_ERROR`.
- No denominator is used, so there is no zero-denominator failure behavior for tracking error.

## Configuration Options
- `options.frequency`
- `options.annualization_factor`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.TRACKING_ERROR.value`
- `results[period].metrics.TRACKING_ERROR.details.aligned_observation_count`
- `results[period].metrics.TRACKING_ERROR.details.annualization_factor`
- `results[period].metrics.TRACKING_ERROR.details.portfolio_mean_return`
- `results[period].metrics.TRACKING_ERROR.details.benchmark_mean_return`
- `results[period].metrics.TRACKING_ERROR.details.active_mean_return`
- `results[period].metrics.TRACKING_ERROR.details.active_volatility`
- `results[period].metrics.TRACKING_ERROR.details.annualized_tracking_error`
- `results[period].metrics.TRACKING_ERROR.details.error`

## Worked Example
Assume no log transform (`options.use_log_returns=false`), daily frequency, default daily
annualization (`AF = 252`), and aligned return observations:

| Date | `Rp_t_used_pp` | `Rb_t_used_pp` | `A_t_pp` |
| --- | ---: | ---: | ---: |
| Day 1 | `1.00` | `0.90` | `0.10` |
| Day 2 | `-0.50` | `-0.30` | `-0.20` |
| Day 3 | `0.20` | `0.10` | `0.10` |

Intermediate calculations:

| Step | Value |
| --- | ---: |
| Mean portfolio return, pp | `0.2333333333` |
| Mean benchmark return, pp | `0.2333333333` |
| Mean active return, pp | `0.0000000000` |
| `details.portfolio_mean_return` | `0.0023333333` |
| `details.benchmark_mean_return` | `0.0023333333` |
| `details.active_mean_return` | `0.0000000000` |
| Active squared deviations sum | `0.0600000000` |
| Sample active variance, pp (`ddof=1`) | `0.0300000000` |
| `sigma_a_pp` | `0.1732050808` |
| `details.active_volatility = sigma_a_pp / 100` | `0.0017320508` |
| Annualization multiplier | `sqrt(252) = 15.8745078664` |
| `details.annualized_tracking_error` | `0.0274954542` |
| `TE_pp` | `2.7495454169` |

Output mapping:

- `results[period].metrics.TRACKING_ERROR.value = 2.7495454169`
- `results[period].metrics.TRACKING_ERROR.details.aligned_observation_count = 3`
- `results[period].metrics.TRACKING_ERROR.details.annualization_factor = 252`
- `results[period].metrics.TRACKING_ERROR.details.portfolio_mean_return = 0.0023333333`
- `results[period].metrics.TRACKING_ERROR.details.benchmark_mean_return = 0.0023333333`
- `results[period].metrics.TRACKING_ERROR.details.active_mean_return = 0.0000000000`
- `results[period].metrics.TRACKING_ERROR.details.active_volatility = 0.0017320508`
- `results[period].metrics.TRACKING_ERROR.details.annualized_tracking_error = 0.0274954542`
