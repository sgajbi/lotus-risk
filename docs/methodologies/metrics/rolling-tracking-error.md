# Rolling Metric Methodology - Rolling Tracking Error

## Metric
- metric_id: ROLLING_TRACKING_ERROR

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series as dated percentage-point observations.
- Benchmark return series as dated percentage-point observations.
- One or more rolling window lengths.
- Annualization basis.
- Minimum-observation policy.
- Optional time-series emission flag.

## Upstream Data Sources
- Stateless mode: caller-provided `returns` and `benchmark_returns`.
- Stateful mode: `lotus-performance` portfolio and benchmark return series fetched through the governed rolling-metrics integration path.
- `lotus-risk` owns the rolling tracking-error calculation after dated return series are resolved. It does not source benchmark returns from Workbench, Gateway, or manage.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- The engine converts portfolio and benchmark returns to decimal before rolling math:
  `r_decimal = r_pp / 100`.
- Active returns are decimal differences.
- `ROLLING_TRACKING_ERROR` output is an annualized decimal ratio: `0.0275` means `2.75%`.
- Response summary fields (`latest`, `average`, `minimum`, `maximum`, `p05`, `p50`, `p95`) use the same annualized decimal ratio unit.

## Variable Dictionary
- `t`: aligned observation date.
- `Rp_t_pp`: portfolio return on date `t`, in percentage points.
- `Rb_t_pp`: benchmark return on date `t`, in percentage points.
- `Rp_t`: portfolio return on date `t`, as decimal (`Rp_t_pp / 100`).
- `Rb_t`: benchmark return on date `t`, as decimal (`Rb_t_pp / 100`).
- `a_t`: active return on date `t`, as decimal (`Rp_t - Rb_t`).
- `W`: requested rolling window length.
- `min_obs`: minimum observations required for a window result.
- `AF`: annualization basis.
- `sigma_a_t(W)`: sample standard deviation of active returns inside the window ending on date `t`, with `ddof=1`.
- `RTE_t(W)`: rolling tracking error for the window ending on date `t`.

## Methodology and Formulas
1. Convert each portfolio and benchmark observation from pp to decimal:
   `Rp_t = Rp_t_pp / 100` and `Rb_t = Rb_t_pp / 100`.
2. Inner-align portfolio and benchmark series by date for the requested period.
3. Compute the active return series:
   `a_t = Rp_t - Rb_t`.
4. Resolve minimum observations:
   - `min_obs = W` when `min_observations_policy = STRICT`;
   - `min_obs = 2` when `min_observations_policy = ALLOW_PARTIAL`.
5. For each date with at least `min_obs` observations in the rolling window, compute sample active-return standard deviation:
   `sigma_a_t(W) = std(a_{t-W+1} ... a_t, ddof=1)`.
6. Annualize:
   `RTE_t(W) = sigma_a_t(W) * sqrt(AF)`.
7. Build summary statistics from computed, non-null `RTE_t(W)` values only.

## Step-by-Step Computation
1. Resolve each requested period from `scope.as_of_date` and the period definition.
2. Filter portfolio and benchmark returns to the period.
3. Convert both filtered series from percentage points to decimal.
4. Inner-align the decimal series by date.
5. If no aligned observations remain, emit no computed metric values and record the benchmark dependency as `NO_ALIGNED_OBSERVATIONS`.
6. For each requested window length, compute the rolling active-return sample standard deviation using `ddof=1`.
7. Annualize each computed point with `sqrt(rolling_options.annualization_basis)`.
8. Leave warm-up points as null until the configured minimum observation count is met.
9. Populate `metric_summaries.ROLLING_TRACKING_ERROR` from non-null annualized values.
10. When `include_time_series=true`, emit `metric_series[].metric_values.ROLLING_TRACKING_ERROR` for every point in the rolling result, with warm-up points represented as null.

## Validation and Failure Behavior
- Stateless requests that include `ROLLING_TRACKING_ERROR` without `benchmark_returns` fail request validation.
- Stateful requests require benchmark-return sourcing from `lotus-performance`; unavailable upstream data is surfaced through dependency/supportability posture rather than local fallback data.
- Fewer than two portfolio observations in the period returns period-level `error = "Insufficient data"` and no window results.
- Benchmark series supplied but with no aligned dates returns `benchmark_context.reason = "NO_ALIGNED_OBSERVATIONS"` and emits no computed tracking-error values for the metric.
- Window warm-up points are null until `min_obs` is met.
- Constant active returns are valid and produce `0.0`; there is no denominator and no zero-variance error for tracking error.
- Non-numeric return values are rejected by request-contract validation before engine math.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.annualization_basis`
- `rolling_options.min_observations_policy`
- `rolling_options.include_time_series`

## Outputs
- `window_results[].metric_summaries.ROLLING_TRACKING_ERROR`
- `window_results[].metric_series[]`
- `results[period].quality_flags`

## Worked Example
Assume daily annualization (`AF = 252`), `STRICT` minimum observations, `W = 3`, and aligned return observations:

| Date | `Rp_t_pp` | `Rb_t_pp` | `Rp_t` | `Rb_t` | `a_t = Rp_t - Rb_t` |
| --- | ---: | ---: | ---: | ---: | ---: |
| Day 1 | `1.00` | `0.80` | `0.010` | `0.008` | `0.002` |
| Day 2 | `-2.00` | `-1.50` | `-0.020` | `-0.015` | `-0.005` |
| Day 3 | `0.50` | `0.40` | `0.005` | `0.004` | `0.001` |

Intermediate calculations for the first full window:

| Step | Value |
| --- | ---: |
| Active mean | `(-0.002) / 3 = -0.0006666667` |
| Squared deviations sum | `0.0000286667` |
| Sample variance (`ddof=1`) | `0.0000143333` |
| `sigma_a_t(3)` | `0.0037859389` |
| Annualization multiplier | `sqrt(252) = 15.8745078664` |
| `RTE_t(3)` | `0.0601026522` |

Output mapping:

- `results[period].window_results[0].metric_summaries.ROLLING_TRACKING_ERROR.latest = 0.0601026522`
- when `include_time_series=true`, the Day 3 point is emitted as
  `metric_series[].metric_values.ROLLING_TRACKING_ERROR = 0.0601026522`
