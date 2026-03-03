# Risk Metric Methodology - Volatility

## Metric
- metric_id: VOLATILITY

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return observations for the resolved period (minimum 2).
- Annualization basis from frequency or explicit override.
- Optional log-return transform flag.

## Upstream Data Sources
- Stateless: caller `returns[]`.
- Stateful: lotus-performance return series.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Variable Dictionary
- `t`: observation index in chronological order.
- `r_t_pp`: portfolio return at `t` in percentage points.
- `r_t_pp*`: transformed return used for volatility calculation (`raw` or `log`).
- `n`: number of observations used in the metric.
- `mu_pp`: arithmetic mean of transformed pp returns.
- `sigma_pp`: sample standard deviation of transformed pp returns (`ddof=1`).
- `AF`: annualization factor.
- `VOL`: annualized volatility output.

## Methodology and Formulas
1. Optional log transform:
- if `use_log_returns=false`: `r_t_pp* = r_t_pp`
- if `use_log_returns=true`: `r_t_pp* = ln(1 + r_t_pp/100) * 100`
2. Sample standard deviation:
`sigma_pp = std(r_t_pp*, ddof=1)`.
3. Annualization:
`VOL = sigma_pp * sqrt(AF)`.
4. Annualization factor resolution:
- `AF = options.annualization_factor` when provided;
- otherwise from frequency map (`DAILY=252`, `WEEKLY=52`, `MONTHLY=12`).

## Step-by-Step Computation
1. Resolve period and filter returns to date window.
2. Apply frequency resampling when requested (weekly/monthly compounding).
3. Resolve annualization factor (`AF`) from override or frequency default.
4. Apply optional log-return transform to produce `r_t_pp*`.
5. Validate at least two observations after filtering/transforms.
6. Compute `sigma_pp` using sample standard deviation (`ddof=1`).
7. Compute annualized volatility `VOL = sigma_pp * sqrt(AF)`.
8. Return value in `metrics.VOLATILITY.value`.

## Validation and Failure Behavior
- Fewer than 2 observations after period filtering/resampling: `details.error = "Insufficient data"`.
- Invalid return values (non-numeric): rejected by request-contract validation before engine math.
- If all transformed returns are identical, `sigma_pp = 0` and output volatility is `0`.
- Frequency resampling happens before standard deviation, so the observation count can change materially.

## Configuration Options
- `options.frequency`
- `options.annualization_factor`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.VOLATILITY.value`
- `results[period].metrics.VOLATILITY.details.error`

## Worked Example
Assume no log transform (`use_log_returns=false`) and daily annualization (`AF=252`).

| Date | `r_t_pp` | `r_t_pp*` used in std | `r_t_pp* - mu_pp` | `(r_t_pp* - mu_pp)^2` |
|---|---:|---:|---:|---:|
| Day1 | 1.00 | 1.00 | 0.7667 | 0.5878 |
| Day2 | -0.50 | -0.50 | -0.7333 | 0.5378 |
| Day3 | 0.20 | 0.20 | -0.0333 | 0.0011 |

Intermediate calculations:
- `mu_pp = (1.00 + (-0.50) + 0.20) / 3 = 0.2333`
- Sum of squared deviations `= 0.5878 + 0.5378 + 0.0011 = 1.1267`
- Sample variance `= 1.1267 / (3-1) = 0.5633`
- `sigma_pp = sqrt(0.5633) = 0.7505`
- `VOL = 0.7505 * sqrt(252) = 11.914`

Output mapping:
- `results[period].metrics.VOLATILITY.value = 11.914`
