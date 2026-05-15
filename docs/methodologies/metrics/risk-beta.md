# Risk Metric Methodology - Beta

## Metric
- metric_id: BETA

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return observations for the resolved period, with at least two aligned observations
  after period filtering and frequency resampling.
- Benchmark return observations for the same resolved period, with at least two aligned
  observations after filtering and resampling.
- Calculation frequency: `DAILY`, `WEEKLY`, or `MONTHLY`.
- Optional log-return transform flag.

## Upstream Data Sources
- Stateless mode: caller-provided `returns` and `benchmark_returns`.
- Stateful mode: `lotus-performance` portfolio and benchmark return series fetched through the
  governed risk-calculate integration path.
- `lotus-risk` owns the beta calculation after dated portfolio and benchmark return series are
  resolved. It does not source portfolio returns, benchmark returns, or beta assumptions from
  Workbench, Gateway, or manage.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Frequency resampling compounds percentage-point returns and emits percentage-point period
  returns.
- If `options.use_log_returns=true`, both portfolio and benchmark returns are transformed with
  `r_log_pp = ln(1 + r_pp / 100) * 100` before alignment.
- Mean-return details are stored as decimal ratios:
  `details.portfolio_mean_return = mean(Rp_used_pp) / 100` and
  `details.benchmark_mean_return = mean(Rb_used_pp) / 100`.
- Covariance and benchmark variance details are computed in percentage-point squared units:
  `details.covariance = cov(Rp_used_pp, Rb_used_pp, ddof=1)` and
  `details.benchmark_variance = var(Rb_used_pp, ddof=1)`.
- `metrics.BETA.value` is a dimensionless slope coefficient.

## Variable Dictionary
- `t`: aligned observation date after strict inner date alignment.
- `Rp_t_pp`: portfolio return on date `t`, in percentage points.
- `Rb_t_pp`: benchmark return on date `t`, in percentage points.
- `Rp_t_used_pp`: portfolio return used for beta after optional log transformation, in
  percentage points.
- `Rb_t_used_pp`: benchmark return used for beta after optional log transformation, in
  percentage points.
- `n_aligned`: number of aligned portfolio/benchmark observations.
- `mu_p_decimal`: mean portfolio return as a decimal ratio.
- `mu_b_decimal`: mean benchmark return as a decimal ratio.
- `Cov_pb_pp2`: sample covariance between portfolio and benchmark used returns, with `ddof=1`.
- `Var_b_pp2`: sample benchmark variance of used returns, with `ddof=1`.
- `BETA`: dimensionless beta slope coefficient.

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
7. Compute the sample covariance matrix with `ddof=1`:
   - `Cov_pb_pp2 = cov(Rp_used_pp, Rb_used_pp, ddof=1)`;
   - `Var_b_pp2 = var(Rb_used_pp, ddof=1)`.
8. Require `Var_b_pp2` to be non-zero under `np.isclose`.
9. Compute beta:
   `BETA = Cov_pb_pp2 / Var_b_pp2`.

## Step-by-Step Computation
1. Build dated portfolio and benchmark return series and sort both by date.
2. Resolve each requested period.
3. Filter both return series to the period date range.
4. Apply weekly or monthly compounding to both series when requested.
5. Apply log-return transformation to both series when requested.
6. Inner-align both series by date.
7. Validate that at least two aligned observations remain.
8. Compute `details.portfolio_mean_return` and `details.benchmark_mean_return` as decimal ratios.
9. Compute `details.covariance` and `details.benchmark_variance` from percentage-point used
   returns with `ddof=1`.
10. Compute `metrics.BETA.value` as the dimensionless slope coefficient.
11. Preserve `details.aligned_observation_count` for auditability.

## Validation and Failure Behavior
- Missing benchmark returns for `BETA` return `metrics.BETA.value = null` with
  `details.error = "Benchmark returns required for benchmark-dependent metric"`.
- Fewer than two aligned observations after period filtering, resampling, and optional
  transformation return `metrics.BETA.value = null` with
  `details.error = "Insufficient aligned observations"`.
- Zero or near-zero benchmark variance returns `metrics.BETA.value = null` with
  `details.error = "Benchmark variance is zero"`.
- Non-numeric return values are rejected by request-contract validation before engine math.
- No risk-free dependency is required for `BETA`.
- The denominator is `Var_b_pp2`; zero denominator is fail-closed and is not promoted as a valid
  ratio.

## Configuration Options
- `options.frequency`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.BETA.value`
- `results[period].metrics.BETA.details.aligned_observation_count`
- `results[period].metrics.BETA.details.portfolio_mean_return`
- `results[period].metrics.BETA.details.benchmark_mean_return`
- `results[period].metrics.BETA.details.covariance`
- `results[period].metrics.BETA.details.benchmark_variance`
- `results[period].metrics.BETA.details.error`

## Worked Example
Assume no log transform (`options.use_log_returns=false`), daily frequency, and aligned return
observations:

| Date | `Rp_t_used_pp` | `Rb_t_used_pp` |
| --- | ---: | ---: |
| Day 1 | `1.00` | `0.50` |
| Day 2 | `-1.00` | `-0.50` |
| Day 3 | `2.00` | `1.00` |

Intermediate calculations:

| Step | Value |
| --- | ---: |
| Mean portfolio return, pp | `0.6666666667` |
| Mean benchmark return, pp | `0.3333333333` |
| `details.portfolio_mean_return` | `0.0066666667` |
| `details.benchmark_mean_return` | `0.0033333333` |
| Product of deviations sum | `2.3333333333` |
| `details.covariance = Cov_pb_pp2` | `1.1666666667` |
| Benchmark squared deviations sum | `1.1666666667` |
| `details.benchmark_variance = Var_b_pp2` | `0.5833333333` |
| `BETA = Cov_pb_pp2 / Var_b_pp2` | `2.0000000000` |

Output mapping:

- `results[period].metrics.BETA.value = 2.0000000000`
- `results[period].metrics.BETA.details.aligned_observation_count = 3`
- `results[period].metrics.BETA.details.portfolio_mean_return = 0.0066666667`
- `results[period].metrics.BETA.details.benchmark_mean_return = 0.0033333333`
- `results[period].metrics.BETA.details.covariance = 1.1666666667`
- `results[period].metrics.BETA.details.benchmark_variance = 0.5833333333`
