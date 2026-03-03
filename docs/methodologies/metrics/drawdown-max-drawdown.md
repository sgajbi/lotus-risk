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

## Methodology and Formulas
1. Convert API returns to decimal:
- `r_t(decimal) = r_t(percentage_points) / 100`

2. Build cumulative wealth path:
- `wealth_t = ∏(1 + r_i)`, for `i=1..t`

3. Build running peak path:
- `peak_t = max(wealth_1..wealth_t)`

4. Build underwater (drawdown) series:
- `drawdown_t = (wealth_t / peak_t) - 1`

5. Compute maximum drawdown:
- `MAX_DRAWDOWN = min_t(drawdown_t)`
- Result is negative or zero.

6. Peak/trough/recovery attribution:
- episode starts when drawdown moves below zero
- trough is minimum drawdown point in that episode
- recovery is first date where drawdown returns to `>= 0`
- if not recovered before period end, recovery date is `null`

## Step-by-Step Computation
1. Resolve the analysis period and extract portfolio returns for that period.
2. Convert return values from percentage-point contract units to decimal.
3. Build cumulative wealth path (`wealth_t`), running peak path (`peak_t`), and drawdown path (`drawdown_t`).
4. Select `min(drawdown_t)` as `MAX_DRAWDOWN`.
5. Identify episode boundaries and map peak/trough/recovery dates for summary fields.
6. Return metric values and episode metadata in response fields.

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
- Input returns (percentage points): Day1 `+5.00`, Day2 `-10.00`, Day3 `+2.00`, Day4 `+4.00`.
- Convert to decimal: `[0.0500, -0.1000, 0.0200, 0.0400]`.
- Wealth path: `[1.050000, 0.945000, 0.963900, 1.002456]`; running peak stays `[1.050000, 1.050000, 1.050000, 1.050000]`.
- Drawdown path (`wealth/peak - 1`): `[0.000000, -0.100000, -0.082000, -0.045280]`.
- Maximum drawdown is `-0.100000` (equivalent to `-10.00%`), with peak Day1 and trough Day2.
