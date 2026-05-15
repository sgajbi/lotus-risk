# Risk Metric Methodology - Volatility

## Metric
- metric_id: VOLATILITY

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return observations for the resolved period, with at least two observations after
  period filtering and frequency resampling.
- Calculation frequency: `DAILY`, `WEEKLY`, or `MONTHLY`.
- Optional annualization-factor override.
- Optional log-return transform flag.

## Upstream Data Sources
- Stateless mode: caller-provided `returns`.
- Stateful mode: `lotus-performance` portfolio return series fetched through the governed
  risk-calculate integration path.
- `lotus-risk` owns the volatility calculation after dated portfolio return series are resolved.
  It does not source portfolio returns from Workbench, Gateway, or manage.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Frequency resampling compounds percentage-point returns and emits percentage-point period
  returns.
- If `options.use_log_returns=true`, the engine transforms percentage-point returns with
  `r_log_pp = ln(1 + r_pp / 100) * 100`.
- The sample standard deviation detail is stored as a decimal ratio:
  `details.standard_deviation = std(r_used_pp, ddof=1) / 100`.
- `metrics.VOLATILITY.value` is an annualized percentage-point output:
  `11.9147` means `11.9147%`.

## Variable Dictionary
- `t`: observation date.
- `r_t_pp`: portfolio return on date `t`, in percentage points.
- `r_t_used_pp`: return used for volatility after optional log transformation, in percentage
  points.
- `n`: number of observations after period filtering, resampling, and optional log transformation.
- `AF`: annualization factor.
- `sigma_pp`: sample standard deviation of `r_t_used_pp` with `ddof=1`, in percentage points.
- `sigma_decimal`: `sigma_pp / 100`.
- `VOL_pp`: annualized volatility output in percentage points.

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
6. Require at least two non-null observations.
7. Compute sample standard deviation:
   `sigma_pp = std(r_t_used_pp, ddof=1)`.
8. Convert the detail value to decimal:
   `sigma_decimal = sigma_pp / 100`.
9. Annualize and map the response value:
   `VOL_pp = sigma_decimal * sqrt(AF) * 100`.

## Step-by-Step Computation
1. Build a dated portfolio-return series and sort by date.
2. Resolve each requested period.
3. Filter the return series to the period date range.
4. Apply weekly or monthly compounding when requested.
5. Apply log-return transformation when requested.
6. Validate that at least two observations remain.
7. Compute `details.standard_deviation` as decimal sample standard deviation.
8. Compute `metrics.VOLATILITY.value` as annualized percentage points.
9. Preserve `details.observation_count` and `details.annualization_factor` for auditability.

## Validation and Failure Behavior
- Fewer than two observations after period filtering, resampling, and optional transformation
  returns `metrics.VOLATILITY.value = null` with `details.error = "Insufficient data"`.
- Constant transformed returns are valid and produce `0.0`.
- Non-numeric return values are rejected by request-contract validation before engine math.
- No benchmark or risk-free dependency is required for `VOLATILITY`.
- No denominator is used, so there is no zero-denominator quality flag for this metric.

## Configuration Options
- `options.frequency`
- `options.annualization_factor`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.VOLATILITY.value`
- `results[period].metrics.VOLATILITY.details.standard_deviation`
- `results[period].metrics.VOLATILITY.details.observation_count`
- `results[period].metrics.VOLATILITY.details.annualization_factor`
- `results[period].metrics.VOLATILITY.details.error`

## Worked Example
Assume no log transform (`options.use_log_returns=false`), daily frequency, default daily
annualization (`AF = 252`), and portfolio return observations:

| Date | `r_t_pp` | `r_t_used_pp` |
| --- | ---: | ---: |
| Day 1 | `1.00` | `1.00` |
| Day 2 | `-0.50` | `-0.50` |
| Day 3 | `0.20` | `0.20` |

Intermediate calculations:

| Step | Value |
| --- | ---: |
| Mean return, pp | `0.2333333333` |
| Squared deviations sum | `1.1266666667` |
| Sample variance, pp (`ddof=1`) | `0.5633333333` |
| `sigma_pp` | `0.7505553499` |
| `details.standard_deviation = sigma_pp / 100` | `0.0075055535` |
| Annualization multiplier | `sqrt(252) = 15.8745078664` |
| `VOL_pp` | `11.9146968069` |

Output mapping:

- `results[period].metrics.VOLATILITY.value = 11.9146968069`
- `results[period].metrics.VOLATILITY.details.standard_deviation = 0.0075055535`
- `results[period].metrics.VOLATILITY.details.observation_count = 3`
- `results[period].metrics.VOLATILITY.details.annualization_factor = 252`
