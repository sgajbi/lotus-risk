# Rolling Metric Methodology - Rolling Maximum Drawdown

## Metric
- metric_id: ROLLING_MAX_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series as dated percentage-point observations.
- One or more rolling window lengths.
- Minimum-observation policy.
- Optional time-series emission flag.

## Upstream Data Sources
- Stateless mode: caller-provided `returns`.
- Stateful mode: `lotus-performance` portfolio return series fetched through the governed
  rolling-metrics integration path.
- `lotus-risk` owns the rolling maximum drawdown calculation after dated portfolio return series
  are resolved. It does not source portfolio returns from Workbench, Gateway, or manage.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- The engine converts portfolio returns to decimal before rolling drawdown math:
  `r_decimal = r_pp / 100`.
- `rolling_options.annualization_basis` is accepted on the shared rolling contract but is not used by `ROLLING_MAX_DRAWDOWN`.
- `ROLLING_MAX_DRAWDOWN` output is a decimal drawdown ratio: `-0.1000` means `-10.00%`.
- Response summary fields (`latest`, `average`, `minimum`, `maximum`, `p05`, `p50`, `p95`) use the
  same decimal drawdown ratio unit.

## Variable Dictionary
- `t`: observation date.
- `Rp_t_pp`: portfolio return on date `t`, in percentage points.
- `Rp_t`: portfolio return on date `t`, as decimal (`Rp_t_pp / 100`).
- `W`: requested rolling window length.
- `min_obs`: minimum observations required for a window result.
- `k`: observation index inside the rolling window.
- `C_k`: cumulative wealth path inside the window through index `k`.
- `P_k`: running peak cumulative wealth through index `k`.
- `DD_k`: drawdown at index `k`.
- `RMDD_t(W)`: rolling maximum drawdown for the window ending on date `t`.

## Methodology and Formulas
1. Convert each portfolio observation from pp to decimal:
   `Rp_t = Rp_t_pp / 100`.
2. Resolve minimum observations:
   - `min_obs = W` when `min_observations_policy = STRICT`;
   - `min_obs = 2` when `min_observations_policy = ALLOW_PARTIAL`.
3. For each date with at least `min_obs` observations in the rolling window, build the cumulative
   wealth path from the window's decimal returns:
   `C_k = product(1 + Rp_i)` for all observations from the start of the window through `k`.
4. Compute the running peak:
   `P_k = max(C_1 ... C_k)`.
5. Compute the drawdown path:
   `DD_k = C_k / P_k - 1`.
6. Select the minimum drawdown in the window:
   `RMDD_t(W) = min(DD_k)`.
7. Build summary statistics from computed, non-null `RMDD_t(W)` values only.

## Step-by-Step Computation
1. Resolve each requested period from `scope.as_of_date` and the period definition.
2. Filter portfolio returns to the period.
3. Convert the filtered series from percentage points to decimal.
4. For each requested window length, apply the rolling maximum drawdown function to each eligible
   rolling window.
5. Leave warm-up points as null until the configured minimum observation count is met.
6. Populate `metric_summaries.ROLLING_MAX_DRAWDOWN` from non-null decimal drawdown values.
7. When `include_time_series=true`, emit `metric_series[].metric_values.ROLLING_MAX_DRAWDOWN` for
   every point in the rolling result, with warm-up points represented as null.

## Validation and Failure Behavior
- Fewer than two portfolio observations in the period returns period-level
  `error = "Insufficient data"` and no window results.
- Window warm-up points are null until `min_obs` is met.
- All-positive or non-declining wealth windows are valid and produce `0.0`.
- Non-numeric return values are rejected by request-contract validation before engine math.
- No benchmark or risk-free dependency is required for `ROLLING_MAX_DRAWDOWN`.
- No denominator is used, so there is no zero-denominator quality flag for this metric.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.min_observations_policy`
- `rolling_options.include_time_series`

## Outputs
- `window_results[].metric_summaries.ROLLING_MAX_DRAWDOWN`
- `window_results[].metric_series[]`
- `results[period].quality_flags`

## Worked Example
Assume `STRICT` minimum observations, `W = 3`, and portfolio return observations:

| Date | `Rp_t_pp` | `Rp_t = Rp_t_pp / 100` |
| --- | ---: | ---: |
| Day 1 | `5.00` | `0.050` |
| Day 2 | `-10.00` | `-0.100` |
| Day 3 | `2.00` | `0.020` |

Intermediate calculations for the first full window:

| Step | Day 1 | Day 2 | Day 3 |
| --- | ---: | ---: | ---: |
| Cumulative wealth `C_k` | `1.0500000000` | `0.9450000000` | `0.9639000000` |
| Running peak `P_k` | `1.0500000000` | `1.0500000000` | `1.0500000000` |
| Drawdown `DD_k` | `0.0000000000` | `-0.1000000000` | `-0.0820000000` |

Output mapping:

- `results[period].window_results[0].metric_summaries.ROLLING_MAX_DRAWDOWN.latest = -0.1000000000`
- when `include_time_series=true`, the Day 3 point is emitted as
  `metric_series[].metric_values.ROLLING_MAX_DRAWDOWN = -0.1000000000`
