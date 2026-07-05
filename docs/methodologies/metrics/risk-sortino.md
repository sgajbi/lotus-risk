# Risk Metric Methodology - Sortino Ratio

## Metric
- metric_id: SORTINO

## Endpoint and Mode Coverage
- endpoint: `/analytics/risk/calculate`
- supported_modes: stateless, stateful
- source product: `RiskMetricsReport:v1`

## Inputs
- Portfolio return observations in percentage points.
- Request periods resolved by the risk calculation contract.
- `options.frequency` for optional return compounding before metric calculation.
- `options.use_log_returns` for optional log-return transformation after frequency compounding.
- `options.mar_annual_rate` as the annual minimum acceptable return.
- Optional `options.annualization_factor` override.

## Upstream Data Sources
- Stateless callers provide return observations directly in the request.
- Stateful mode resolves return observations from `lotus-performance`.
- No benchmark dependency is required for `SORTINO`.
- No risk-free dependency is required for `SORTINO`; MAR is supplied separately through risk
  options.

## Unit Conventions
- Return inputs are percentage points: `1.0` means `+1%`.
- Frequency resampling compounds percentage-point returns before metric calculation:
  `r_resampled_pp = ((product(1 + r_raw_pp / 100)) - 1) * 100`.
- When log returns are enabled, the transformed return remains in percentage points:
  `r_log_pp = ln(1 + r_pp / 100) * 100`.
- Mean return, periodic MAR, excess return, annualized excess return, and downside deviation in
  `details` are decimals.
- `metrics.SORTINO.value` is a dimensionless annualized ratio.

## Variable Dictionary
- `t`: aligned observation index in chronological order.
- `r_raw_t_pp`: raw portfolio return at `t`, in percentage points.
- `r_used_t_pp`: portfolio return used by the metric after frequency compounding and optional
  log-return transformation, in percentage points.
- `r_used_t_dec`: `r_used_t_pp / 100`.
- `AF`: annualization factor.
- `MAR_annual`: annual minimum acceptable return from `options.mar_annual_rate`, in decimal units.
- `MAR_periodic`: periodic minimum acceptable return, in decimal units.
- `x_t`: excess return versus periodic MAR, `r_used_t_dec - MAR_periodic`.
- `D`: downside excess-return set containing all `x_t < 0`.
- `N`: count of all portfolio observations used by the metric.
- `N_down`: count of downside observations in `D`.
- `mu_dec`: arithmetic mean of all `r_used_t_dec`.
- `mu_excess_dec`: `mu_dec - MAR_periodic`.
- `sigma_down_dec`: downside deviation, computed as `sqrt(mean(x_t^2 for x_t in D))`.
- `SORTINO`: annualized Sortino ratio.

## Methodology and Formulas
1. Resolve the requested period window.
2. Filter portfolio returns to the period window.
3. Apply `options.frequency`:
   - `DAILY`: use daily observations as supplied.
   - `WEEKLY`: compound observations into Friday-ending weekly returns.
   - `MONTHLY`: compound observations into month-end returns.
4. Apply optional log-return transformation:
   - when `use_log_returns=false`, `r_used_t_pp = r_resampled_t_pp`;
   - when `use_log_returns=true`, `r_used_t_pp = ln(1 + r_resampled_t_pp / 100) * 100`.
5. Resolve annualization factor:
   - use `options.annualization_factor` when supplied;
   - otherwise `AF = 252` for `DAILY`, `52` for `WEEKLY`, and `12` for `MONTHLY`.
6. Convert annual MAR to periodic MAR:
   `MAR_periodic = (1 + MAR_annual)^(1 / AF) - 1`.
7. Convert the used returns to decimals:
   `r_used_t_dec = r_used_t_pp / 100`.
8. Compute downside excess returns:
   `x_t = r_used_t_dec - MAR_periodic`.
9. Build downside set:
   `D = {x_t | x_t < 0}`.
10. Compute downside deviation:
    `sigma_down_dec = sqrt(mean(x_t^2 for x_t in D))`.
11. Compute full-sample mean excess return:
    `mu_excess_dec = mean(r_used_t_dec) - MAR_periodic`.
12. Compute dimensionless annualized Sortino ratio:
    `SORTINO = (mu_excess_dec / sigma_down_dec) * sqrt(AF)`.

## Step-by-Step Computation
1. Resolve the period start/end dates from the request period and portfolio open date.
2. Select portfolio returns within the resolved period.
3. Compound returns to the requested frequency when frequency is not `DAILY`.
4. Apply optional log-return transformation.
5. Require at least two observations after filtering, frequency compounding, and optional
   transformation.
6. Resolve `AF` and `MAR_periodic`.
7. Convert used percentage-point returns to decimals.
8. Compute `x_t` for every observation.
9. Keep only negative `x_t` values in downside set `D`.
10. Fail closed when `D` is empty.
11. Compute `sigma_down_dec` as root-mean-square downside excess return.
12. Compute full-sample `mu_excess_dec`, annualized excess return, and Sortino output.
13. Populate metric value and details fields.

## Validation and Failure Behavior
- Fewer than two portfolio observations after period filtering, frequency compounding, and optional
  transformation return `metrics.SORTINO.value = null` with `details.error = "Insufficient data"`.
- Empty downside set after MAR comparison returns `metrics.SORTINO.value = null` with
  `details.error = "No downside observations"`.
- Non-numeric return values are rejected by request validation before engine math.
- When `options.use_log_returns=true`, any compounded portfolio return less than or equal to
  `-100%` returns `metrics.SORTINO.value = null` with
  `details.error = "Log returns are undefined for returns less than or equal to -100%"`.
- No benchmark dependency is required for `SORTINO`.
- No risk-free dependency is required for `SORTINO`.
- The denominator is `sigma_down_dec`; it is computed only from downside excess returns and is not
  annualized before the ratio calculation.

## Configuration Options
- `options.frequency`
- `options.use_log_returns`
- `options.mar_annual_rate`
- `options.annualization_factor`

## Outputs
- `results[period].metrics.SORTINO.value`
- `results[period].metrics.SORTINO.details.observation_count`
- `results[period].metrics.SORTINO.details.annualization_factor`
- `results[period].metrics.SORTINO.details.mar_annual_rate`
- `results[period].metrics.SORTINO.details.periodic_mar`
- `results[period].metrics.SORTINO.details.mean_return`
- `results[period].metrics.SORTINO.details.excess_return`
- `results[period].metrics.SORTINO.details.annualized_excess_return`
- `results[period].metrics.SORTINO.details.downside_observation_count`
- `results[period].metrics.SORTINO.details.downside_deviation`
- `results[period].metrics.SORTINO.details.error`

## Worked Example
Assume:
- returns (pp): `[1.00, -0.50, 0.20, -0.10]`
- `MAR_annual = 0.02`
- `AF = 252`
- `use_log_returns = false`

| Date | `r_used_t_pp` | `r_used_t_dec` | `MAR_periodic` | `x_t = r_used_t_dec - MAR_periodic` | In `D`? | `x_t^2` if in `D` |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| 2026-01-01 | 1.00 | 0.0100000000 | 0.0000785849 | 0.0099214151 | No | - |
| 2026-01-02 | -0.50 | -0.0050000000 | 0.0000785849 | -0.0050785849 | Yes | 0.0000257920 |
| 2026-01-03 | 0.20 | 0.0020000000 | 0.0000785849 | 0.0019214151 | No | - |
| 2026-01-04 | -0.10 | -0.0010000000 | 0.0000785849 | -0.0010785849 | Yes | 0.0000011633 |

Intermediate calculations:
- `N = 4`
- `N_down = 2`
- `MAR_periodic = (1 + 0.02)^(1 / 252) - 1 = 0.0000785849`
- `mu_dec = mean([0.0100000000, -0.0050000000, 0.0020000000, -0.0010000000]) = 0.0015000000`
- `mu_excess_dec = 0.0015000000 - 0.0000785849 = 0.0014214151`
- `annualized_excess_return = 0.0014214151 * 252 = 0.3581965946`
- `sigma_down_dec = sqrt(mean([0.0000257920, 0.0000011633])) = 0.0036711967`
- `SORTINO = (0.0014214151 / 0.0036711967) * sqrt(252) = 6.1462967894`

Output mapping:
- `results[period].metrics.SORTINO.value = 6.1462967894`
- `results[period].metrics.SORTINO.details.observation_count = 4`
- `results[period].metrics.SORTINO.details.annualization_factor = 252`
- `results[period].metrics.SORTINO.details.mar_annual_rate = 0.0200000000`
- `results[period].metrics.SORTINO.details.periodic_mar = 0.0000785849`
- `results[period].metrics.SORTINO.details.mean_return = 0.0015000000`
- `results[period].metrics.SORTINO.details.excess_return = 0.0014214151`
- `results[period].metrics.SORTINO.details.annualized_excess_return = 0.3581965946`
- `results[period].metrics.SORTINO.details.downside_observation_count = 2`
- `results[period].metrics.SORTINO.details.downside_deviation = 0.0036711967`
