# Drawdown Methodology - Maximum Drawdown

## Metric
- metric_id: MAX_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful
- source product: `DrawdownAnalyticsReport:v1`

## Inputs
- Portfolio return observations for the resolved period.
- Return contract unit: percentage points (`value=1.0` means `+1%`).
- Period boundaries after period resolution (`EXPLICIT`, `YEAR`, `YTD`, `QTD`, `MTD`, `1Y`, `3Y`,
  `5Y`, or `SI`).
- Drawdown analysis options controlling duration convention, underwater-series inclusion, and
  episode-list filtering.

## Upstream Data Sources
- Stateless mode: caller-provided `stateless_input.returns[]`.
- Stateful mode: `lotus-risk` sources `series.portfolio_returns` from
  `lotus-performance` `/integration/returns/series` through the governed drawdown stateful
  adapter.
- `lotus-risk` owns the maximum-drawdown calculation after dated portfolio return series are
  resolved. It does not source portfolio returns from Workbench, Gateway, or manage.

## Unit Conventions
- Input return values are percentage points: `5.0` means `+5.0%`.
- The engine converts percentage-point returns to decimal only inside the wealth path:
  `r_decimal = r_pp / 100`.
- `summary.max_drawdown` and episode `depth` values are decimal drawdown ratios:
  `-0.2000` means a `-20.00%` peak-to-trough drawdown.
- `analysis_options.duration_unit` changes day counters only; it does not change the drawdown
  ratio.
- `analysis_options.top_n_episodes` and `analysis_options.minimum_episode_depth_bps` filter the
  optional episode list only; they do not change `summary.max_drawdown`.

## Variable Dictionary
- `t`: observation date.
- `r_t_pp`: portfolio return on date `t`, in percentage points.
- `r_t_decimal`: `r_t_pp / 100`.
- `W_t`: cumulative wealth index through date `t`, `product(1 + r_i_decimal)` for `i <= t`.
- `P_t`: running peak wealth through date `t`, `max(W_i)` for `i <= t`.
- `DD_t`: decimal drawdown ratio on date `t`, `W_t / P_t - 1`.
- `E`: set of drawdown episodes, where an episode starts when `DD_t < 0` after a non-underwater
  observation and ends when `DD_t >= 0` or period end is reached.
- `depth_e`: minimum `DD_t` inside episode `e`.
- `MDD`: maximum drawdown summary value, `min(depth_e)` when episodes exist, otherwise `0.0`.

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
8. Extract episodes from the drawdown path:
   - a new episode starts at the first underwater observation where `DD_t < 0`;
   - `peak_date` is the previous observation date when one exists, otherwise the underwater date;
   - `trough_date` is the date of the minimum `DD_t` in the episode;
   - `recovery_date` is the first date in that episode where `DD_t >= 0`; unrecovered episodes use
     `null`.
9. Select the maximum-drawdown episode:
   `max_episode = argmin(depth_e)`.
10. Map summary output:
    `summary.max_drawdown = depth_max_episode`.

## Step-by-Step Computation
1. Build a dated portfolio-return series and sort by date.
2. Resolve each requested period.
3. Filter the return series to the period date range.
4. Return a period-level `"Insufficient data"` error when the filtered period is empty.
5. Compute cumulative wealth, running peak, and drawdown paths.
6. Build all drawdown episodes from contiguous underwater spans.
7. Compute `summary.max_drawdown` from the deepest episode.
8. Preserve peak date, trough date, recovery date, recovery flag, days-to-trough,
   days-to-recovery, and time-under-water fields from the selected deepest episode.
9. Build optional `episodes[]` from filtered/sorted episodes when `include_episode_list=true`.
10. Build optional `underwater_series[]` when `include_underwater_series=true`.

## Validation and Failure Behavior
- Empty service-level return input returns an empty `results` map.
- Empty return series for a requested period returns that period with `summary = null`,
  `episodes = []`, and `error = "Insufficient data"`.
- A one-observation or never-underwater period is valid and emits `summary.max_drawdown = 0.0`,
  no peak/trough/recovery dates, `is_recovered = true`, and zero day counters.
- Non-numeric return entries are rejected by request-contract validation before engine math.
- Episode recovery not reached before period end emits `max_drawdown_recovery_date = null`,
  `is_recovered = false`, and `days_to_recovery = null`.
- `analysis_options.duration_unit` changes `days_to_trough`, `days_to_recovery`, and episode
  `total_days` only.
- `analysis_options.top_n_episodes` and `analysis_options.minimum_episode_depth_bps` do not alter
  `summary.max_drawdown`.

## Configuration Options
- `analysis_options.duration_unit`
- `analysis_options.include_underwater_series`
- `analysis_options.include_episode_list`
- `analysis_options.top_n_episodes`
- `analysis_options.minimum_episode_depth_bps`

## Outputs
- `results[period].summary.max_drawdown`
- `results[period].summary.max_drawdown_peak_date`
- `results[period].summary.max_drawdown_trough_date`
- `results[period].summary.max_drawdown_recovery_date`
- `results[period].summary.is_recovered`
- `results[period].summary.days_to_trough`
- `results[period].summary.days_to_recovery`
- `results[period].summary.time_under_water_days`
- `results[period].episodes[].depth`
- `results[period].underwater_series[].drawdown`
- `results[period].error`

## Worked Example
Assume business-day duration, `include_episode_list=true`, `include_underwater_series=true`, and
portfolio return observations:

| Date | `r_t_pp` | `W_t` | `P_t` | `DD_t` |
| --- | ---: | ---: | ---: | ---: |
| 2026-01-02 | `10.00` | `1.1000000000` | `1.1000000000` | `0.0000000000` |
| 2026-01-05 | `-20.00` | `0.8800000000` | `1.1000000000` | `-0.2000000000` |
| 2026-01-06 | `30.00` | `1.1440000000` | `1.1440000000` | `0.0000000000` |

Intermediate calculations:

| Step | Value |
| --- | ---: |
| Episode start date | `2026-01-05` |
| Episode peak date | `2026-01-02` |
| Episode trough date | `2026-01-05` |
| Episode recovery date | `2026-01-06` |
| Episode depth | `-0.2000000000` |
| `summary.max_drawdown` | `-0.2000000000` |
| Business days from peak to trough | `1` |
| Business days from trough to recovery | `1` |

Output mapping:

- `results[period].summary.max_drawdown = -0.2000000000`
- `results[period].summary.max_drawdown_peak_date = "2026-01-02"`
- `results[period].summary.max_drawdown_trough_date = "2026-01-05"`
- `results[period].summary.max_drawdown_recovery_date = "2026-01-06"`
- `results[period].summary.is_recovered = true`
- `results[period].summary.days_to_trough = 1`
- `results[period].summary.days_to_recovery = 1`
- `results[period].summary.time_under_water_days = 1`
- `results[period].episodes[0].depth = -0.2000000000`
- `results[period].underwater_series[1].drawdown = -0.2000000000`
