# Drawdown Methodology - Maximum Drawdown

## Metric
- metric_id: MAX_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Portfolio return time series for the resolved period.
- Return contract unit: percentage points (`value=1.0` means `+1%`).
- Period boundaries after period resolution (`EXPLICIT`, `YEAR`, `YTD`, etc.).

## Upstream Data Sources
- Stateless:
  - caller provides `stateless_input.returns[]`.
- Stateful:
  - lotus-risk sources `series.portfolio_returns` from lotus-performance `/integration/returns/series`.

## Unit Conventions
- Input return values are provided in percentage points in the API contract.
- Engine computation normalizes to decimal for wealth-path math:
  - `r_decimal = r_percentage_points / 100`
- `MAX_DRAWDOWN` output is in decimal drawdown units (for example `-0.10` means `-10%`).

## Variable Dictionary
- `t`: observation index in chronological order.
- `r_t_pp`: period return at index `t` in percentage points.
- `r_t`: period return at index `t` in decimal (`r_t = r_t_pp / 100`).
- `W_t`: cumulative wealth index up to `t`.
- `P_t`: running peak wealth up to `t`.
- `DD_t`: drawdown at `t`.
- `MDD`: maximum drawdown over the analysis window.

## Methodology and Formulas
1. Convert returns from pp to decimal:
`r_t = r_t_pp / 100`.
2. Construct cumulative wealth path:
`W_t = ∏_{i=1..t}(1 + r_i)`.
3. Construct running peak path:
`P_t = max(W_1, W_2, ..., W_t)`.
4. Construct drawdown path:
`DD_t = (W_t / P_t) - 1`.
5. Maximum drawdown:
`MDD = min_t(DD_t)`.
6. Episode attribution:
- Peak date is the date of `argmax(W_i)` over `i <= trough_index`.
- Trough date is the date of `argmin(DD_t)`.
- Recovery date is first date after trough where `DD_t >= 0`; else `null`.

## Step-by-Step Computation
1. Resolve the analysis period and extract portfolio returns for that period.
2. Sort observations ascending by date; discard points outside the resolved period.
3. Validate minimum data:
- if no points are present, period result is returned with error (`Insufficient data`);
- if only one point exists, drawdown path is degenerate and summary fields follow engine fallback.
4. Convert pp returns to decimal.
5. Compute `W_t`, `P_t`, and `DD_t` for each date.
6. Compute `MDD = min_t(DD_t)`.
7. Find trough index from `argmin(DD_t)`.
8. Find peak index from `argmax(W_i)` where `i <= trough_index`.
9. Determine recovery date as first post-trough date with `DD_t >= 0`, else `null`.
10. Map values into response summary fields.

## Validation and Failure Behavior
- Missing return series for the period: return period error `Insufficient data`.
- Non-numeric return entries: rejected at request-contract validation layer before engine math.
- Episode recovery not reached before period end: `max_drawdown_recovery_date = null`, `is_recovered = false`.
- Configuration options (`top_n_episodes`, `minimum_episode_depth_bps`) do not alter numeric `max_drawdown`, only episode list payload.

## Configuration Options
- `analysis_options.duration_unit`:
  - controls episode day counters (`BUSINESS_DAYS` vs `CALENDAR_DAYS`)
  - does not change numeric `MAX_DRAWDOWN`.
- `analysis_options.include_episode_list`:
  - controls whether episodes are emitted in response
  - does not change summary max drawdown value.
- `analysis_options.top_n_episodes` and `analysis_options.minimum_episode_depth_bps`:
  - affect episode list selection
  - do not change summary max drawdown value.

## Outputs
- `results[period].summary.max_drawdown`
- `results[period].summary.max_drawdown_peak_date`
- `results[period].summary.max_drawdown_trough_date`
- `results[period].summary.max_drawdown_recovery_date`
- `results[period].summary.is_recovered`
- `results[period].summary.days_to_trough`
- `results[period].summary.days_to_recovery`

## Worked Example
Input return sequence (pp): Day1 `+5.00`, Day2 `-10.00`, Day3 `+2.00`, Day4 `+4.00`.

| Date | `r_t_pp` | `r_t` (decimal) | `W_t` | `P_t` | `DD_t = W_t/P_t - 1` |
|---|---:|---:|---:|---:|---:|
| Day1 | 5.00 | 0.0500 | 1.050000 | 1.050000 | 0.000000 |
| Day2 | -10.00 | -0.1000 | 0.945000 | 1.050000 | -0.100000 |
| Day3 | 2.00 | 0.0200 | 0.963900 | 1.050000 | -0.082000 |
| Day4 | 4.00 | 0.0400 | 1.002456 | 1.050000 | -0.045280 |

Derived outputs:
- `max_drawdown = min(DD_t) = -0.100000` (`-10.00%`).
- `max_drawdown_peak_date = Day1`.
- `max_drawdown_trough_date = Day2`.
- `max_drawdown_recovery_date = null` (drawdown never returned to `>= 0` by Day4).
- `is_recovered = false`.
