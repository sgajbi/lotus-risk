# Risk Metric Methodology - Sharpe Ratio

## Metric
- metric_id: SHARPE

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return observations for the resolved period, with at least two observations after
  period filtering and frequency resampling.
- Calculation frequency: `DAILY`, `WEEKLY`, or `MONTHLY`.
- Optional annualization-factor override.
- Optional log-return transform flag.
- Risk-free mode and optional annual risk-free rate.

## Upstream Data Sources
- Stateless mode: caller-provided `returns`.
- Stateful mode: `lotus-performance` portfolio return series fetched through the governed
  risk-calculate integration path.
- Stateful Sharpe can derive risk-free evidence through the governed risk-free source path when
  the stateful adapter receives risk-free points; the engine itself consumes only the resolved
  `options.risk_free_mode` and `options.risk_free_annual_rate`.
- `lotus-risk` owns the Sharpe calculation after dated portfolio returns and risk-free settings
  are resolved. It does not source portfolio returns or risk-free assumptions from Workbench,
  Gateway, or manage.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Frequency resampling compounds percentage-point returns and emits percentage-point period
  returns.
- If `options.use_log_returns=true`, the engine transforms percentage-point returns with
  `r_log_pp = ln(1 + r_pp / 100) * 100`.
- Mean return and volatility details are stored as decimal ratios:
  `details.mean_return = mean(r_used_pp) / 100` and
  `details.volatility = std(r_used_pp, ddof=1) / 100`.
- When `options.risk_free_mode=ANNUAL_RATE`, the periodic risk-free rate is a decimal ratio:
  `details.periodic_risk_free_rate = (1 + rf_annual)^(1 / AF) - 1`.
- `metrics.SHARPE.value` is a dimensionless annualized ratio.

## Variable Dictionary
- `t`: observation date.
- `r_t_pp`: portfolio return on date `t`, in percentage points.
- `r_t_used_pp`: return used for Sharpe after optional log transformation, in percentage points.
- `n`: number of observations after period filtering, resampling, and optional log transformation.
- `AF`: annualization factor.
- `rf_annual`: annual risk-free rate as a decimal ratio when
  `options.risk_free_mode=ANNUAL_RATE`.
- `rf_p`: periodic risk-free rate as a decimal ratio.
- `mu_decimal`: arithmetic mean of `r_t_used_pp`, divided by `100`.
- `sigma_decimal`: sample standard deviation of `r_t_used_pp` with `ddof=1`, divided by `100`.
- `excess_decimal`: `mu_decimal - rf_p`.
- `SHARPE`: annualized Sharpe ratio.

## Methodology and Formulas
1. Resolve the requested period from `scope.as_of_date`, `portfolio_open_date`, and the period
   definition.
2. Filter portfolio returns to the resolved period.
3. Resample returns when `options.frequency` is not `DAILY`:
   `r_period_pp = (product(1 + r_i_pp / 100) - 1) * 100`.
4. Apply the optional log-return transform:
   - when `options.use_log_returns=false`, `r_t_used_pp = r_t_pp`;
   - when `options.use_log_returns=true`, `r_t_used_pp = ln(1 + r_t_pp / 100) * 100`.
5. Resolve annualization factor:
   - `AF = options.annualization_factor` when supplied;
   - otherwise `AF = 252` for `DAILY`, `52` for `WEEKLY`, and `12` for `MONTHLY`.
6. Resolve periodic risk-free rate:
   - when `options.risk_free_mode=ZERO`, `rf_p = 0`;
   - when `options.risk_free_mode=ANNUAL_RATE`,
     `rf_p = (1 + rf_annual)^(1 / AF) - 1`.
7. Require at least two non-null observations.
8. Compute mean and sample standard deviation:
   - `mu_decimal = mean(r_t_used_pp) / 100`;
   - `sigma_decimal = std(r_t_used_pp, ddof=1) / 100`.
9. Require `sigma_decimal` to be non-zero.
10. Compute annualized Sharpe:
    `SHARPE = ((mu_decimal - rf_p) / sigma_decimal) * sqrt(AF)`.

## Step-by-Step Computation
1. Build a dated portfolio-return series and sort by date.
2. Resolve each requested period.
3. Filter the return series to the period date range.
4. Apply weekly or monthly compounding when requested.
5. Apply log-return transformation when requested.
6. Resolve `AF` and `rf_p`.
7. Validate that at least two observations remain.
8. Compute `details.mean_return`, `details.volatility`, `details.periodic_risk_free_rate`, and
   `details.excess_return` as decimal ratios.
9. Compute `metrics.SHARPE.value` as a dimensionless annualized ratio.
10. Preserve `details.observation_count`, `details.annualization_factor`, and
    `details.annualized_excess_return` for auditability.

## Validation and Failure Behavior
- Fewer than two observations after period filtering, resampling, and optional transformation
  returns `metrics.SHARPE.value = null` with `details.error = "Insufficient data"`.
- When `options.use_log_returns=true`, any compounded portfolio return less than or equal to
  `-100%` returns `metrics.SHARPE.value = null` with
  `details.error = "Log returns are undefined for returns less than or equal to -100%"`.
- `options.risk_free_mode=ANNUAL_RATE` requires `options.risk_free_annual_rate` at request
  validation.
- Zero sample volatility returns `metrics.SHARPE.value = null` with
  `details.error = "Zero volatility"`.
- Non-numeric return values are rejected by request-contract validation before engine math.
- No benchmark dependency is required for `SHARPE`.
- The denominator is `sigma_decimal`; zero denominator is fail-closed and is not promoted as a
  valid ratio.

## Configuration Options
- `options.frequency`
- `options.annualization_factor`
- `options.use_log_returns`
- `options.risk_free_mode`
- `options.risk_free_annual_rate`

## Outputs
- `results[period].metrics.SHARPE.value`
- `results[period].metrics.SHARPE.details.mean_return`
- `results[period].metrics.SHARPE.details.periodic_risk_free_rate`
- `results[period].metrics.SHARPE.details.excess_return`
- `results[period].metrics.SHARPE.details.annualized_excess_return`
- `results[period].metrics.SHARPE.details.volatility`
- `results[period].metrics.SHARPE.details.observation_count`
- `results[period].metrics.SHARPE.details.annualization_factor`
- `results[period].metrics.SHARPE.details.error`

## Worked Example
Assume no log transform (`options.use_log_returns=false`), daily frequency, default daily
annualization (`AF = 252`), `options.risk_free_mode=ANNUAL_RATE`,
`options.risk_free_annual_rate=0.02`, and portfolio return observations:

| Date | `r_t_pp` | `r_t_used_pp` |
| --- | ---: | ---: |
| Day 1 | `1.00` | `1.00` |
| Day 2 | `-0.50` | `-0.50` |
| Day 3 | `0.20` | `0.20` |

Intermediate calculations:

| Step | Value |
| --- | ---: |
| Mean return, pp | `0.2333333333` |
| `details.mean_return = mean / 100` | `0.0023333333` |
| Squared deviations sum | `1.1266666667` |
| Sample variance, pp (`ddof=1`) | `0.5633333333` |
| `sigma_pp` | `0.7505553499` |
| `details.volatility = sigma_pp / 100` | `0.0075055535` |
| `details.periodic_risk_free_rate` | `0.0000785849` |
| `details.excess_return` | `0.0022547484` |
| Annualization multiplier | `sqrt(252) = 15.8745078664` |
| `SHARPE` | `4.7688716199` |

Output mapping:

- `results[period].metrics.SHARPE.value = 4.7688716199`
- `results[period].metrics.SHARPE.details.mean_return = 0.0023333333`
- `results[period].metrics.SHARPE.details.periodic_risk_free_rate = 0.0000785849`
- `results[period].metrics.SHARPE.details.excess_return = 0.0022547484`
- `results[period].metrics.SHARPE.details.annualized_excess_return = 0.5681965946`
- `results[period].metrics.SHARPE.details.volatility = 0.0075055535`
- `results[period].metrics.SHARPE.details.observation_count = 3`
- `results[period].metrics.SHARPE.details.annualization_factor = 252`
