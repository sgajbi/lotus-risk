# Risk Metric Methodology - Sharpe Ratio

## Metric
- metric_id: SHARPE

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series in pp.
- Risk-free settings and annualization basis.

## Upstream Data Sources
- Stateless caller returns.
- Stateful lotus-performance returns.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Variable Dictionary
- `t`: observation index in chronological order.
- `r_t_pp`: return at `t` in percentage points (possibly log-transformed if configured).
- `mu_pp`: arithmetic mean of `r_t_pp`.
- `sigma_pp`: sample standard deviation of `r_t_pp` (`ddof=1`).
- `AF`: annualization factor.
- `rf_annual`: annual risk-free rate when `risk_free_mode=ANNUAL_RATE`.
- `rf_p`: periodic risk-free rate corresponding to `AF`.
- `mu_excess`: excess mean return in decimal.
- `sigma`: volatility in decimal.
- `SHARPE`: annualized Sharpe ratio.

## Methodology and Formulas
1. Optional return transform:
- if `use_log_returns=false`: use raw pp returns.
- if `use_log_returns=true`: `r_t_pp = ln(1 + r_raw_t_pp/100) * 100`.
2. Resolve annualization factor:
- `AF = options.annualization_factor` when provided;
- else from frequency map (`DAILY=252`, `WEEKLY=52`, `MONTHLY=12`).
3. Resolve periodic risk-free rate:
- if `risk_free_mode=ZERO`: `rf_p = 0`
- if `risk_free_mode=ANNUAL_RATE`: `rf_p = (1 + rf_annual)^(1/AF) - 1`
4. Compute excess mean and volatility (decimal):
- `mu_excess = (mu_pp / 100) - rf_p`
- `sigma = sigma_pp / 100`
5. Compute Sharpe:
- `SHARPE = (mu_excess / sigma) * sqrt(AF)`.

## Step-by-Step Computation
1. Resolve period and filter return observations to the selected window.
2. Apply frequency resampling (if weekly/monthly) and optional log-return transform.
3. Resolve annualization factor (`AF`) and periodic risk-free rate (`rf_p`).
4. Validate at least two observations remain.
5. Compute `mu_pp` and `sigma_pp` on transformed series.
6. Convert mean/std to decimal (`mu_pp/100`, `sigma_pp/100`).
7. Compute `mu_excess` and Sharpe ratio.
8. If `sigma` is zero, emit deterministic metric error `Zero volatility`.
9. Return value in `results[period].metrics.SHARPE.value`.

## Validation and Failure Behavior
- Fewer than 2 observations after filtering/resampling: `details.error = "Insufficient data"`.
- `risk_free_mode=ANNUAL_RATE` without valid annual rate: blocked at request validation.
- `sigma == 0`: `details.error = "Zero volatility"`.
- Non-numeric returns: rejected by request-contract validation before engine math.

## Configuration Options
- `options.risk_free_mode`
- `options.risk_free_annual_rate`
- `options.annualization_factor`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.SHARPE.value`
- `...details.error`

## Worked Example
Assume:
- returns (pp): `[1.00, -0.50, 0.20]`
- `risk_free_mode=ANNUAL_RATE`, `rf_annual=0.02`
- `AF=252`
- `use_log_returns=false`

| Date | `r_t_pp` | `r_t_pp - mu_pp` | `(r_t_pp - mu_pp)^2` |
|---|---:|---:|---:|
| Day1 | 1.00 | 0.7667 | 0.5878 |
| Day2 | -0.50 | -0.7333 | 0.5378 |
| Day3 | 0.20 | -0.0333 | 0.0011 |

Intermediate calculations:
- `mu_pp = (1.00 - 0.50 + 0.20)/3 = 0.2333`
- sample variance `= (0.5878 + 0.5378 + 0.0011)/(3-1) = 0.5633`
- `sigma_pp = sqrt(0.5633) = 0.7505`
- mean decimal `= 0.2333/100 = 0.002333`
- volatility decimal `sigma = 0.7505/100 = 0.007505`
- `rf_p = (1.02)^(1/252) - 1 = 0.0000786`
- `mu_excess = 0.002333 - 0.0000786 = 0.0022544`
- `SHARPE = (0.0022544 / 0.007505) * sqrt(252) = 4.769`

Output mapping:
- `results[period].metrics.SHARPE.value = 4.769`
