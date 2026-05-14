# Rolling Metric Methodology - Rolling Beta

## Metric
- metric_id: ROLLING_BETA

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series as dated percentage-point observations.
- Benchmark return series as dated percentage-point observations.
- One or more rolling window lengths.
- Minimum-observation policy.
- Optional time-series emission flag.

## Upstream Data Sources
- Stateless mode: caller-provided `returns` and `benchmark_returns`.
- Stateful mode: `lotus-performance` provides portfolio and benchmark return series through the governed rolling-metrics integration path.
- `lotus-risk` owns the rolling beta calculation after dated return series are resolved. It does not source benchmark returns from Workbench, Gateway, or manage.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- The engine converts portfolio and benchmark returns to decimal before rolling math:
  `r_decimal = r_pp / 100`.
- `ROLLING_BETA` output is a dimensionless ratio.
- Response summary fields (`latest`, `average`, `minimum`, `maximum`, `p05`, `p50`, `p95`) use the same dimensionless ratio unit.
- `rolling_options.annualization_basis` is accepted on the shared rolling contract but is not used by `ROLLING_BETA`.

## Variable Dictionary
- `t`: aligned observation date.
- `Rp_t_pp`: portfolio return on date `t`, in percentage points.
- `Rb_t_pp`: benchmark return on date `t`, in percentage points.
- `Rp_t`: portfolio return on date `t`, as decimal (`Rp_t_pp / 100`).
- `Rb_t`: benchmark return on date `t`, as decimal (`Rb_t_pp / 100`).
- `W`: requested rolling window length.
- `min_obs`: minimum observations required for a window result.
- `cov_t(W)`: sample covariance of portfolio and benchmark returns inside the window ending on date `t`.
- `var_b_t(W)`: sample variance of benchmark returns inside the window ending on date `t`, with `ddof=1`.
- `RBETA_t(W)`: rolling beta for the window ending on date `t`.

## Methodology and Formulas
1. Convert each portfolio and benchmark observation from pp to decimal:
   `Rp_t = Rp_t_pp / 100` and `Rb_t = Rb_t_pp / 100`.
2. Inner-align portfolio and benchmark series by date for the requested period.
3. Resolve minimum observations:
   - `min_obs = W` when `min_observations_policy = STRICT`;
   - `min_obs = 2` when `min_observations_policy = ALLOW_PARTIAL`.
4. For each date with at least `min_obs` observations in the rolling window, compute:
   - `cov_t(W) = cov(Rp_{t-W+1} ... Rp_t, Rb_{t-W+1} ... Rb_t)`;
   - `var_b_t(W) = var(Rb_{t-W+1} ... Rb_t, ddof=1)`.
5. Compute beta:
   `RBETA_t(W) = cov_t(W) / var_b_t(W)`.
6. Replace infinite results with null before summaries are built.
7. Build summary statistics from computed, non-null `RBETA_t(W)` values only.

## Step-by-Step Computation
1. Resolve each requested period from `scope.as_of_date` and the period definition.
2. Filter portfolio and benchmark returns to the period.
3. Convert both filtered series from percentage points to decimal.
4. Inner-align the decimal series by date.
5. If no aligned observations remain, emit no computed metric values and record the benchmark dependency as `NO_ALIGNED_OBSERVATIONS`.
6. For each requested window length, compute rolling sample covariance and benchmark sample variance.
7. Divide rolling covariance by rolling benchmark variance.
8. Convert infinite values to null so zero benchmark-variance windows do not become misleading beta values.
9. Leave warm-up points as null until the configured minimum observation count is met.
10. Populate `metric_summaries.ROLLING_BETA` from non-null beta values.
11. When `include_time_series=true`, emit `metric_series[].metric_values.ROLLING_BETA` for every point in the rolling result, with warm-up and zero-variance points represented as null.

## Validation and Failure Behavior
- Stateless requests that include `ROLLING_BETA` without `benchmark_returns` fail request validation.
- Stateful requests require benchmark return sourcing from `lotus-performance`; unavailable upstream benchmark data is surfaced through dependency/supportability posture rather than local fallback data.
- Fewer than two portfolio observations in the period returns period-level `error = "Insufficient data"` and no window results.
- Benchmark series supplied but with no aligned dates returns `benchmark_context.reason = "NO_ALIGNED_OBSERVATIONS"` and emits no computed beta values for the metric.
- Window warm-up points are null until `min_obs` is met.
- Zero rolling benchmark variance produces null metric points and quality flag `metric:ROLLING_BETA:benchmark_variance_zero`.
- Non-numeric return values are rejected by request-contract validation before engine math.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.min_observations_policy`
- `rolling_options.include_time_series`

## Outputs
- `window_results[].metric_summaries.ROLLING_BETA`
- `window_results[].metric_series[]`
- `results[period].quality_flags`

## Worked Example
Assume `STRICT` minimum observations, `W = 3`, and aligned return observations:

| Date | `Rp_t_pp` | `Rb_t_pp` | `Rp_t` | `Rb_t` |
| --- | ---: | ---: | ---: | ---: |
| Day 1 | `1.50` | `1.00` | `0.015` | `0.010` |
| Day 2 | `-3.00` | `-2.00` | `-0.030` | `-0.020` |
| Day 3 | `2.25` | `1.50` | `0.0225` | `0.015` |

Intermediate calculations for the first full window:

| Step | Value |
| --- | ---: |
| Portfolio mean | `0.0025000000` |
| Benchmark mean | `0.0016666667` |
| Sample covariance | `0.0005375000` |
| Benchmark sample variance (`ddof=1`) | `0.0003583333` |
| `RBETA_t(3)` | `1.5000000000` |

Output mapping:

- `results[period].window_results[0].metric_summaries.ROLLING_BETA.latest = 1.5000000000`
- when `include_time_series=true`, the Day 3 point is emitted as
  `metric_series[].metric_values.ROLLING_BETA = 1.5000000000`
