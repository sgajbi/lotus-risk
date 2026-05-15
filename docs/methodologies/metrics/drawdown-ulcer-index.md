# Drawdown Methodology - Ulcer Index

## Metric
- metric_id: ULCER_INDEX

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful
- source product: `DrawdownAnalyticsReport:v1`

## Inputs
- Portfolio return observations for the resolved period.
- Return contract unit: percentage points (`value=1.0` means `+1%`).
- Period boundaries after period resolution (`EXPLICIT`, `YEAR`, `YTD`, `QTD`, `MTD`, `1Y`, `3Y`,
  `5Y`, or `SI`).
- Drawdown analysis options controlling underwater-series inclusion, episode-list filtering, and
  duration convention for episode counters.

## Upstream Data Sources
- Stateless mode: caller-provided `stateless_input.returns[]`.
- Stateful mode: `lotus-risk` sources `series.portfolio_returns` from
  `lotus-performance` `/integration/returns/series` through the governed drawdown stateful
  adapter.
- `lotus-risk` owns the ulcer-index calculation after dated portfolio return series are resolved.
  It does not source portfolio returns from Workbench, Gateway, or manage.

## Unit Conventions
- Input return values are percentage points: `5.0` means `+5.0%`.
- The engine converts percentage-point returns to decimal only inside the wealth path:
  `r_decimal = r_pp / 100`.
- `summary.ulcer_index` is a non-negative decimal drawdown ratio:
  `0.06851` means root-mean-square drawdown depth of about `6.851%`.
- Every decimal drawdown observation in the period enters the root-mean-square calculation,
  including peak observations where `DD_t = 0`.
- `analysis_options.duration_unit`, `analysis_options.top_n_episodes`, and
  `analysis_options.minimum_episode_depth_bps` do not change `summary.ulcer_index`.

## Variable Dictionary
- `t`: observation date.
- `r_t_pp`: portfolio return on date `t`, in percentage points.
- `r_t_decimal`: `r_t_pp / 100`.
- `W_t`: cumulative wealth index through date `t`, `product(1 + r_i_decimal)` for `i <= t`.
- `P_t`: running peak wealth through date `t`, `max(W_i)` for `i <= t`.
- `DD_t`: decimal drawdown ratio on date `t`, `W_t / P_t - 1`.
- `S_t`: squared decimal drawdown value, `DD_t^2`.
- `N`: number of drawdown observations in the resolved period.
- `UI`: ulcer-index summary value.

## Methodology and Formulas
1. Resolve the requested period from `scope.as_of_date`, the first return observation date, and the
   period definition.
2. Filter portfolio returns to the resolved period.
3. Require at least one observation in the resolved period; an empty period emits period-level
   error `"Insufficient data"`.
4. Convert percentage-point returns to decimal:
   `r_t_decimal = r_t_pp / 100`.
5. Build cumulative wealth:
   `W_t = product(1 + r_i_decimal)` for `i <= t`.
6. Build running peak wealth:
   `P_t = max(W_i)` for `i <= t`.
7. Build decimal drawdown path:
   `DD_t = W_t / P_t - 1`.
8. Square every drawdown observation:
   `S_t = DD_t^2`.
9. Map summary output:
   `summary.ulcer_index = sqrt(sum(S_t) / N)`.

## Step-by-Step Computation
1. Build a dated portfolio-return series and sort by date.
2. Resolve each requested period.
3. Filter the return series to the period date range.
4. Return a period-level `"Insufficient data"` error when the filtered period is empty.
5. Compute cumulative wealth, running peak, and drawdown paths.
6. Square every decimal drawdown observation, including zero drawdowns at new peaks.
7. Compute the arithmetic mean of the squared drawdown values.
8. Take the square root of that mean.
9. Build optional `episodes[]` and `underwater_series[]` independently from the ulcer-index
   summary value.

## Validation and Failure Behavior
- Empty service-level return input returns an empty `results` map.
- Empty return series for a requested period returns that period with `summary = null`,
  `episodes = []`, and `error = "Insufficient data"`.
- A one-observation or never-underwater period is valid and emits `summary.ulcer_index = 0.0`.
- Non-numeric return entries are rejected by request-contract validation before engine math.
- `summary.ulcer_index` is non-negative by construction.
- `analysis_options.duration_unit` changes episode day counters only.
- `analysis_options.top_n_episodes` and `analysis_options.minimum_episode_depth_bps` do not alter
  `summary.ulcer_index`.

## Configuration Options
- `analysis_options.include_underwater_series`
- `analysis_options.include_episode_list`
- `analysis_options.top_n_episodes`
- `analysis_options.minimum_episode_depth_bps`

## Outputs
- `results[period].summary.ulcer_index`
- `results[period].summary.time_under_water_days`
- `results[period].underwater_series[].drawdown`
- `results[period].error`

## Worked Example
Assume `include_underwater_series=true` and portfolio return observations:

| Date | `r_t_pp` | `W_t` | `P_t` | `DD_t` | `S_t = DD_t^2` |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-01-02 | `5.00` | `1.0500000000` | `1.0500000000` | `0.0000000000` | `0.0000000000` |
| 2026-01-05 | `-10.00` | `0.9450000000` | `1.0500000000` | `-0.1000000000` | `0.0100000000` |
| 2026-01-06 | `2.00` | `0.9639000000` | `1.0500000000` | `-0.0820000000` | `0.0067240000` |
| 2026-01-07 | `4.00` | `1.0024560000` | `1.0500000000` | `-0.0452800000` | `0.0020502784` |

Intermediate calculations:

| Step | Value |
| --- | ---: |
| Observation count `N` | `4` |
| `sum(S_t)` | `0.0187742784` |
| `mean(S_t)` | `0.0046935696` |
| `summary.ulcer_index` | `0.0685096314` |

Output mapping:

- `results[period].summary.ulcer_index = 0.0685096314`
- `results[period].summary.time_under_water_days = 3`
- `results[period].underwater_series[1].drawdown = -0.1000000000`
- `results[period].underwater_series[3].drawdown = -0.0452800000`
