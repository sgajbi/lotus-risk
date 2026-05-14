# Rolling Metric Methodology - Rolling Volatility

## Metric
- metric_id: ROLLING_VOLATILITY

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series as dated percentage-point observations.
- One or more rolling window lengths.
- Annualization basis.
- Minimum-observation policy.
- Optional time-series emission flag.

## Upstream Data Sources
- Stateless mode: caller-provided `returns`.
- Stateful mode: `lotus-performance` portfolio return series fetched through the governed
  rolling-metrics integration path.
- `lotus-risk` owns the rolling volatility calculation after dated return series are resolved. It
  does not source portfolio returns from Workbench, Gateway, or manage.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- The engine converts portfolio returns to decimal before rolling math:
  `r_decimal = r_pp / 100`.
- `ROLLING_VOLATILITY` output is an annualized decimal ratio: `0.3005` means `30.05%`.
- Response summary fields (`latest`, `average`, `minimum`, `maximum`, `p05`, `p50`, `p95`) use the
  same annualized decimal ratio unit.

## Variable Dictionary
- `t`: observation date.
- `Rp_t_pp`: portfolio return on date `t`, in percentage points.
- `Rp_t`: portfolio return on date `t`, as decimal (`Rp_t_pp / 100`).
- `W`: requested rolling window length.
- `min_obs`: minimum observations required for a window result.
- `AF`: annualization basis.
- `sigma_p_t(W)`: sample standard deviation of portfolio returns inside the window ending on date
  `t`, with `ddof=1`.
- `RV_t(W)`: rolling volatility for the window ending on date `t`.

## Methodology and Formulas
1. Convert each portfolio observation from pp to decimal:
   `Rp_t = Rp_t_pp / 100`.
2. Resolve minimum observations:
   - `min_obs = W` when `min_observations_policy = STRICT`;
   - `min_obs = 2` when `min_observations_policy = ALLOW_PARTIAL`.
3. For each date with at least `min_obs` observations in the rolling window, compute sample
   portfolio-return standard deviation:
   `sigma_p_t(W) = std(Rp_{t-W+1} ... Rp_t, ddof=1)`.
4. Annualize:
   `RV_t(W) = sigma_p_t(W) * sqrt(AF)`.
5. Build summary statistics from computed, non-null `RV_t(W)` values only.

## Step-by-Step Computation
1. Resolve each requested period from `scope.as_of_date` and the period definition.
2. Filter portfolio returns to the period.
3. Convert the filtered series from percentage points to decimal.
4. For each requested window length, compute rolling sample standard deviation using `ddof=1`.
5. Annualize each computed point with `sqrt(rolling_options.annualization_basis)`.
6. Leave warm-up points as null until the configured minimum observation count is met.
7. Populate `metric_summaries.ROLLING_VOLATILITY` from non-null annualized values.
8. When `include_time_series=true`, emit `metric_series[].metric_values.ROLLING_VOLATILITY` for
   every point in the rolling result, with warm-up points represented as null.

## Validation and Failure Behavior
- Fewer than two portfolio observations in the period returns period-level
  `error = "Insufficient data"` and no window results.
- Window warm-up points are null until `min_obs` is met.
- Constant portfolio returns are valid and produce `0.0`; there is no denominator and no
  zero-variance error for rolling volatility.
- Non-numeric return values are rejected by request-contract validation before engine math.
- No benchmark or risk-free dependency is required for `ROLLING_VOLATILITY`.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.annualization_basis`
- `rolling_options.min_observations_policy`
- `rolling_options.include_time_series`

## Outputs
- `window_results[].metric_summaries.ROLLING_VOLATILITY`
- `window_results[].metric_series[]`
- `results[period].quality_flags`

## Worked Example
Assume daily annualization (`AF = 252`), `STRICT` minimum observations, `W = 3`, and portfolio return
observations:

| Date | `Rp_t_pp` | `Rp_t = Rp_t_pp / 100` |
| --- | ---: | ---: |
| Day 1 | `1.00` | `0.010` |
| Day 2 | `-2.00` | `-0.020` |
| Day 3 | `1.50` | `0.015` |

Intermediate calculations for the first full window:

| Step | Value |
| --- | ---: |
| Portfolio mean | `0.005 / 3 = 0.0016666667` |
| Squared deviations sum | `0.0007166667` |
| Sample variance (`ddof=1`) | `0.0003583333` |
| `sigma_p_t(3)` | `0.0189296945` |
| Annualization multiplier | `sqrt(252) = 15.8745078664` |
| `RV_t(3)` | `0.3004995840` |

Output mapping:

- `results[period].window_results[0].metric_summaries.ROLLING_VOLATILITY.latest = 0.3004995840`
- when `include_time_series=true`, the Day 3 point is emitted as
  `metric_series[].metric_values.ROLLING_VOLATILITY = 0.3004995840`
