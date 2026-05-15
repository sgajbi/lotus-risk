# Risk Metric Methodology - Drawdown

## Metric
- metric_id: DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful
- source product: `RiskMetricsReport:v1`

## Inputs
- Portfolio return observations for the resolved period, with at least two observations after
  period filtering and frequency resampling.
- Calculation frequency: `DAILY`, `WEEKLY`, or `MONTHLY`.
- Optional log-return transform flag is accepted on the shared risk-calculation contract but is
  not used by `DRAWDOWN`.

## Upstream Data Sources
- Stateless mode: caller-provided `returns`.
- Stateful mode: `lotus-performance` portfolio return series fetched through the governed
  risk-calculate integration path.
- `lotus-risk` owns the drawdown calculation after dated portfolio return series are resolved. It
  does not source portfolio returns from Workbench, Gateway, or manage.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Frequency resampling compounds percentage-point returns and emits percentage-point period
  returns.
- The engine converts percentage-point returns to decimal only inside the cumulative wealth path:
  `r_decimal = r_pp / 100`.
- `options.use_log_returns` is not applied to `DRAWDOWN`; the drawdown path is calculated from the
  simple compounded return series.
- `metrics.DRAWDOWN.value` and `details.max_drawdown` are signed percentage-point outputs:
  `-20.0` means a `-20.0%` maximum peak-to-trough drawdown.

## Variable Dictionary
- `t`: observation date.
- `r_t_pp`: portfolio return on date `t`, in percentage points after period filtering and optional
  frequency resampling.
- `r_t_decimal`: `r_t_pp / 100`.
- `W_t`: cumulative wealth index through date `t`, `product(1 + r_i_decimal)` for `i <= t`.
- `P_t`: running peak wealth through date `t`, `max(W_i)` for `i <= t`.
- `DD_t`: decimal drawdown ratio on date `t`, `W_t / P_t - 1`.
- `T`: trough date where `DD_t` is minimal.
- `P`: peak date selected from the maximum wealth value at or before `T`.
- `MDD_pp`: signed percentage-point maximum drawdown output, `DD_T * 100`.

## Methodology and Formulas
1. Resolve the requested period from `scope.as_of_date`, `portfolio_open_date`, and the period
   definition.
2. Filter portfolio returns to the resolved period.
3. Resample returns when `options.frequency` is not `DAILY`:
   `r_period_pp = (product(1 + r_i_pp / 100) - 1) * 100`.
4. Do not apply `options.use_log_returns`; drawdown uses the simple percentage-point return series.
5. Require at least two non-null observations.
6. Build cumulative wealth:
   `W_t = product(1 + r_i_pp / 100)`.
7. Build running peak wealth:
   `P_t = max(W_i)` for `i <= t`.
8. Compute the drawdown path:
   `DD_t = W_t / P_t - 1`.
9. Select the trough date:
   `T = argmin(DD_t)`.
10. Select the peak date from the maximum wealth value at or before `T`.
11. Map response value and details:
    `metrics.DRAWDOWN.value = details.max_drawdown = DD_T * 100`.

## Step-by-Step Computation
1. Build a dated portfolio-return series and sort by date.
2. Resolve each requested period.
3. Filter the return series to the period date range.
4. Apply weekly or monthly compounding when requested.
5. Validate that at least two observations remain.
6. Compute cumulative wealth, running peak, and decimal drawdown paths.
7. Identify the trough date where drawdown is most negative.
8. Identify the peak date as the maximum cumulative wealth at or before the trough.
9. Search for the first post-trough recovery date where wealth is greater than or equal to the
   trough-date running peak.
10. Preserve signed percentage-point drawdown value and episode timing details for auditability.

## Validation and Failure Behavior
- Fewer than two observations after period filtering and resampling returns
  `metrics.DRAWDOWN.value = null` with `details.error = "Insufficient data"`.
- A non-loss path is valid and produces `metrics.DRAWDOWN.value = 0.0`.
- Non-numeric return values are rejected by request-contract validation before engine math.
- No benchmark dependency is required for `DRAWDOWN`.
- No risk-free dependency is required for `DRAWDOWN`.
- No annualization factor is used for `DRAWDOWN`.
- No denominator is used beyond the running peak wealth path, so there is no zero-volatility,
  zero-tracking-error, or zero-benchmark-variance failure mode.

## Configuration Options
- `options.frequency`

## Outputs
- `results[period].metrics.DRAWDOWN.value`
- `results[period].metrics.DRAWDOWN.details.max_drawdown`
- `results[period].metrics.DRAWDOWN.details.peak_date`
- `results[period].metrics.DRAWDOWN.details.trough_date`
- `results[period].metrics.DRAWDOWN.details.max_drawdown_date`
- `results[period].metrics.DRAWDOWN.details.recovery_date`
- `results[period].metrics.DRAWDOWN.details.is_recovered`
- `results[period].metrics.DRAWDOWN.details.days_to_trough`
- `results[period].metrics.DRAWDOWN.details.days_to_recovery`
- `results[period].metrics.DRAWDOWN.details.time_under_water_days`
- `results[period].metrics.DRAWDOWN.details.error`

## Worked Example
Assume daily frequency and portfolio return observations:

| Date | `r_t_pp` | `W_t` | `P_t` | `DD_t` |
| --- | ---: | ---: | ---: | ---: |
| 2026-01-01 | `10.00` | `1.1000000000` | `1.1000000000` | `0.0000000000` |
| 2026-01-02 | `-20.00` | `0.8800000000` | `1.1000000000` | `-0.2000000000` |
| 2026-01-03 | `5.00` | `0.9240000000` | `1.1000000000` | `-0.1600000000` |

Intermediate calculations:

| Step | Value |
| --- | ---: |
| Trough date | `2026-01-02` |
| Peak date at or before trough | `2026-01-01` |
| Minimum decimal drawdown `DD_T` | `-0.2000000000` |
| `MDD_pp = DD_T * 100` | `-20.0000000000` |
| Recovered by period end | `false` |
| Days from peak to trough | `1` |
| Time under water through period end | `2` |

Output mapping:

- `results[period].metrics.DRAWDOWN.value = -20.0000000000`
- `results[period].metrics.DRAWDOWN.details.max_drawdown = -20.0000000000`
- `results[period].metrics.DRAWDOWN.details.peak_date = "2026-01-01"`
- `results[period].metrics.DRAWDOWN.details.trough_date = "2026-01-02"`
- `results[period].metrics.DRAWDOWN.details.max_drawdown_date = "2026-01-02"`
- `results[period].metrics.DRAWDOWN.details.recovery_date = null`
- `results[period].metrics.DRAWDOWN.details.is_recovered = false`
- `results[period].metrics.DRAWDOWN.details.days_to_trough = 1`
- `results[period].metrics.DRAWDOWN.details.days_to_recovery = null`
- `results[period].metrics.DRAWDOWN.details.time_under_water_days = 2`
