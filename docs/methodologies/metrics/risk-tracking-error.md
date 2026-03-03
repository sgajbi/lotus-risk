# Risk Metric Methodology - Tracking Error

## Metric
- metric_id: TRACKING_ERROR

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio and benchmark returns.
- Annualization basis.

## Upstream Data Sources
- Stateless caller.
- Stateful lotus-performance.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Variable Dictionary
- `t`: aligned observation index over common portfolio/benchmark dates.
- `Rp_t_pp`: portfolio return at `t` in percentage points (post-transform if log mode is used).
- `Rb_t_pp`: benchmark return at `t` in percentage points (post-transform if log mode is used).
- `a_t_pp`: active return in percentage points (`a_t_pp = Rp_t_pp - Rb_t_pp`).
- `mu_a_pp`: mean of active pp returns.
- `sigma_a_pp`: sample standard deviation of active pp returns (`ddof=1`).
- `AF`: annualization factor.
- `TE`: annualized tracking error.

## Methodology and Formulas
1. Optional return transform:
- if `use_log_returns=false`: use raw pp returns
- if `use_log_returns=true`: transform each series as `ln(1 + r_pp/100) * 100`
2. Align portfolio and benchmark returns by date (inner join).
3. Compute active return series in pp:
`a_t_pp = Rp_t_pp - Rb_t_pp`.
4. Compute sample active standard deviation:
`sigma_a_pp = std(a_t_pp, ddof=1)`.
5. Resolve annualization factor:
- `AF = options.annualization_factor` when provided;
- else from frequency map (`DAILY=252`, `WEEKLY=52`, `MONTHLY=12`).
6. Compute annualized tracking error:
`TE = sigma_a_pp * sqrt(AF)`.

## Step-by-Step Computation
1. Resolve period and filter portfolio and benchmark series to date window.
2. Apply configured frequency resampling to both series.
3. Apply optional log-return transform to both series.
4. Inner-align on dates and build active return vector `a_t_pp`.
5. Validate at least two aligned observations (`Insufficient data` if not).
6. Compute sample standard deviation `sigma_a_pp` with `ddof=1`.
7. Resolve annualization factor (`AF`) and compute `TE = sigma_a_pp * sqrt(AF)`.
8. Return value in `results[period].metrics.TRACKING_ERROR.value`.

## Validation and Failure Behavior
- Missing benchmark series for benchmark-dependent metrics: `details.error = "Benchmark returns required for benchmark-dependent metric"`.
- Fewer than 2 aligned observations: `details.error = "Insufficient data"`.
- Non-numeric return values: rejected by request-contract validation before engine math.
- If active returns are constant, `sigma_a_pp = 0` and tracking error is `0`.

## Configuration Options
- `options.frequency`
- `options.annualization_factor`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.TRACKING_ERROR.value`
- `results[period].metrics.TRACKING_ERROR.details.error`

## Worked Example
Assume aligned returns (pp), no log transform, daily annualization (`AF=252`):
- Portfolio: `[1.00, -0.50, 0.20]`
- Benchmark: `[0.90, -0.30, 0.10]`
- Active: `[0.10, -0.20, 0.10]`

| Date | `Rp_t_pp` | `Rb_t_pp` | `a_t_pp = Rp_t_pp - Rb_t_pp` | `a_t_pp - mu_a_pp` | `(a_t_pp - mu_a_pp)^2` |
|---|---:|---:|---:|---:|---:|
| Day1 | 1.00 | 0.90 | 0.10 | 0.10 | 0.0100 |
| Day2 | -0.50 | -0.30 | -0.20 | -0.20 | 0.0400 |
| Day3 | 0.20 | 0.10 | 0.10 | 0.10 | 0.0100 |

Intermediate calculations:
- `mu_a_pp = (0.10 - 0.20 + 0.10)/3 = 0.00`
- sample variance `= (0.0100 + 0.0400 + 0.0100)/(3-1) = 0.0300`
- `sigma_a_pp = sqrt(0.0300) = 0.1732`
- `TE = 0.1732 * sqrt(252) = 2.7495`

Output mapping:
- `results[period].metrics.TRACKING_ERROR.value = 2.7495`
