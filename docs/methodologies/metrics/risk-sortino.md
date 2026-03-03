# Risk Metric Methodology - Sortino Ratio

## Metric
- metric_id: SORTINO

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series in pp.
- Minimum acceptable return annual rate.

## Upstream Data Sources
- Stateless caller returns.
- Stateful lotus-performance returns.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Variable Dictionary
- `t`: observation index in chronological order.
- `r_t_pp`: portfolio return at `t` in percentage points (post-transform if log mode is used).
- `AF`: annualization factor.
- `mar_annual`: annual minimum acceptable return from options.
- `mar_p`: periodic MAR threshold in decimal.
- `x_t`: excess return vs MAR in decimal (`x_t = r_t_pp/100 - mar_p`).
- `D`: downside set, all `x_t < 0`.
- `sigma_down`: downside deviation (`sqrt(mean(D^2))`).
- `mu_excess`: mean excess return vs MAR in decimal.
- `SORTINO`: annualized Sortino ratio.

## Methodology and Formulas
1. Optional return transform:
- if `use_log_returns=false`: use raw `r_t_pp`
- if `use_log_returns=true`: `r_t_pp = ln(1 + r_raw_t_pp/100) * 100`
2. Resolve annualization factor:
- `AF = options.annualization_factor` when provided;
- else from frequency map (`DAILY=252`, `WEEKLY=52`, `MONTHLY=12`).
3. Convert annual MAR to periodic MAR:
`mar_p = (1 + mar_annual)^(1/AF) - 1`.
4. Compute excess return series:
`x_t = r_t_pp/100 - mar_p`.
5. Construct downside set:
`D = {x_t | x_t < 0}`.
6. Compute downside deviation:
`sigma_down = sqrt(mean(D^2))`.
7. Compute mean excess return:
`mu_excess = mean(r_t_pp)/100 - mar_p`.
8. Compute Sortino:
`SORTINO = (mu_excess / sigma_down) * sqrt(AF)`.

## Step-by-Step Computation
1. Resolve period and filter return observations to the selected window.
2. Apply frequency resampling and optional log-return transform.
3. Resolve annualization factor and compute periodic MAR threshold.
4. Compute excess return series `x_t`.
5. Build downside set `D` from values where `x_t < 0`.
6. If `D` is empty, emit deterministic metric error `No downside observations`.
7. Compute downside deviation from `D`.
8. Compute `mu_excess` from full return sample (not downside-only sample).
9. Compute annualized Sortino and map to response.

## Validation and Failure Behavior
- Fewer than 2 observations after filtering/resampling: `details.error = "Insufficient data"`.
- Empty downside set `D`: `details.error = "No downside observations"`.
- Non-numeric return values: rejected by request-contract validation before engine math.
- `options.mar_annual_rate` is required/validated at request-contract layer.

## Configuration Options
- `options.mar_annual_rate`
- `options.annualization_factor`

## Outputs
- `results[period].metrics.SORTINO.value`
- `...details.error`

## Worked Example
Assume:
- returns (pp): `[1.00, -2.00, 0.50]`
- `mar_annual = 0.00`, `AF = 252`
- `use_log_returns = false`

| Date | `r_t_pp` | `r_t_pp/100` | `mar_p` | `x_t = r_t_pp/100 - mar_p` | In downside set `D`? | `x_t^2` if in `D` |
|---|---:|---:|---:|---:|---|---:|
| Day1 | 1.00 | 0.0100 | 0.0000 | 0.0100 | No | - |
| Day2 | -2.00 | -0.0200 | 0.0000 | -0.0200 | Yes | 0.000400 |
| Day3 | 0.50 | 0.0050 | 0.0000 | 0.0050 | No | - |

Intermediate calculations:
- `D = [-0.0200]`
- `sigma_down = sqrt(mean([0.000400])) = 0.0200`
- `mu_excess = mean([0.0100, -0.0200, 0.0050]) - 0.0000 = -0.001667`
- `SORTINO = (-0.001667 / 0.0200) * sqrt(252) = -1.323`

Output mapping:
- `results[period].metrics.SORTINO.value = -1.323`
