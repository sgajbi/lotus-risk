# Risk Metric Methodology - Information Ratio

## Metric
- metric_id: INFORMATION_RATIO

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
- `mu_a_pp`: arithmetic mean of active pp returns.
- `sigma_a_pp`: sample standard deviation of active pp returns (`ddof=1`).
- `AF`: annualization factor.
- `IR`: annualized information ratio.

## Methodology and Formulas
1. Optional return transform:
- if `use_log_returns=false`: use raw pp returns
- if `use_log_returns=true`: transform each series as `ln(1 + r_pp/100) * 100`
2. Align portfolio and benchmark returns by date (inner join).
3. Compute active return series in pp:
`a_t_pp = Rp_t_pp - Rb_t_pp`.
4. Compute sample active moments:
- `mu_a_pp = mean(a_t_pp)`
- `sigma_a_pp = std(a_t_pp, ddof=1)`
5. Resolve annualization factor:
- `AF = options.annualization_factor` when provided;
- else from frequency map (`DAILY=252`, `WEEKLY=52`, `MONTHLY=12`).
6. Information ratio:
`IR = (mu_a_pp / sigma_a_pp) * sqrt(AF)`.
7. If `sigma_a_pp` is numerically zero (`np.isclose`), emit error instead of value.

## Step-by-Step Computation
1. Resolve period and filter portfolio and benchmark series to the selected date window.
2. Apply configured frequency resampling to both series.
3. Apply optional log-return transform to both series.
4. Inner-align on dates and build active return vector `a_t_pp`.
5. Validate at least two aligned observations (`Insufficient data` if not).
6. Compute `mu_a_pp` and `sigma_a_pp` on active returns (`ddof=1`).
7. If `sigma_a_pp` is near zero, emit `Tracking error is zero`.
8. Resolve annualization factor `AF` and compute `IR`.
9. Return value in `results[period].metrics.INFORMATION_RATIO.value`.

## Validation and Failure Behavior
- Missing benchmark series for benchmark-dependent metrics: `details.error = "Benchmark returns required for benchmark-dependent metric"`.
- Fewer than 2 aligned observations: `details.error = "Insufficient data"`.
- Near-zero active standard deviation: `details.error = "Tracking error is zero"`.
- Non-numeric return values: rejected by request-contract validation before engine math.
- Alignment is strict inner join; non-overlapping dates are dropped before metric computation.

## Configuration Options
- `options.frequency`
- `options.annualization_factor`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.INFORMATION_RATIO.value`
- `results[period].metrics.INFORMATION_RATIO.details.error`

## Worked Example
Assume aligned returns (pp), no log transform, daily annualization (`AF=252`):
- Portfolio: `[1.00, -0.50, 0.20, 0.00]`
- Benchmark: `[0.80, -0.60, 0.30, 0.00]`
- Active: `[0.20, 0.10, -0.10, 0.00]`

| Date | `Rp_t_pp` | `Rb_t_pp` | `a_t_pp = Rp_t_pp - Rb_t_pp` | `a_t_pp - mu_a_pp` | `(a_t_pp - mu_a_pp)^2` |
|---|---:|---:|---:|---:|---:|
| Day1 | 1.00 | 0.80 | 0.20 | 0.15 | 0.0225 |
| Day2 | -0.50 | -0.60 | 0.10 | 0.05 | 0.0025 |
| Day3 | 0.20 | 0.30 | -0.10 | -0.15 | 0.0225 |
| Day4 | 0.00 | 0.00 | 0.00 | -0.05 | 0.0025 |

Intermediate calculations:
- `mu_a_pp = (0.20 + 0.10 - 0.10 + 0.00) / 4 = 0.05`
- sample variance `= (0.0225 + 0.0025 + 0.0225 + 0.0025) / (4-1) = 0.016667`
- `sigma_a_pp = sqrt(0.016667) = 0.1291`
- `IR = (0.05 / 0.1291) * sqrt(252) = 6.147`

Output mapping:
- `results[period].metrics.INFORMATION_RATIO.value = 6.147`
