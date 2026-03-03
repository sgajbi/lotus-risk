# Risk Metric Methodology - Beta

## Metric
- metric_id: BETA

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio and benchmark return series in pp.

## Upstream Data Sources
- Stateless caller provides both.
- Stateful lotus-performance provides both.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Variable Dictionary
- `t`: aligned observation index over common portfolio/benchmark dates.
- `Rp_t_pp`: portfolio return at `t` in percentage points (post-transform if log mode is used).
- `Rb_t_pp`: benchmark return at `t` in percentage points (post-transform if log mode is used).
- `Cov_pb`: sample covariance between portfolio and benchmark (`ddof=1`).
- `Var_b`: sample benchmark variance (`ddof=1`).
- `BETA`: beta slope coefficient (`Cov_pb / Var_b`).

## Methodology and Formulas
1. Optional return transform:
- if `use_log_returns=false`: use raw pp returns
- if `use_log_returns=true`: transform each series using `ln(1 + r_pp/100) * 100`
2. Align portfolio and benchmark returns by date (inner join).
3. Compute sample covariance matrix with `ddof=1`.
4. Extract covariance and benchmark variance:
- `Cov_pb = cov(Rp, Rb)`
- `Var_b = var(Rb)`
5. Compute beta:
`BETA = Cov_pb / Var_b`
6. If `Var_b` is numerically zero (`np.isclose`), emit error instead of value.

## Step-by-Step Computation
1. Resolve period and filter portfolio and benchmark series to date window.
2. Apply configured frequency resampling to both series.
3. Apply optional log-return transform to both series.
4. Inner-align on dates and build two-column matrix (`portfolio`, `benchmark`).
5. Validate minimum data (`>=2` aligned observations); else emit `Insufficient data`.
6. Compute covariance matrix via `np.cov(..., ddof=1)`.
7. Read denominator as benchmark variance (`matrix[1,1]`).
8. If denominator is near zero, emit `Benchmark variance is zero`.
9. Else compute and return beta.

## Validation and Failure Behavior
- Missing benchmark series for benchmark-dependent metrics: `details.error = "Benchmark returns required for benchmark-dependent metric"`.
- Fewer than 2 aligned observations: `details.error = "Insufficient data"`.
- Near-zero benchmark variance: `details.error = "Benchmark variance is zero"`.
- Non-numeric return entries: rejected by request-contract validation before engine computation.
- Alignment is strict inner join, so non-overlapping dates are dropped.

## Configuration Options
- `options.frequency`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.BETA.value`
- `...details.error`

## Worked Example
Assume aligned returns (pp), no log transform:
- Portfolio: `[1.0, -1.0, 2.0]`
- Benchmark: `[0.5, -0.5, 1.0]`

| Date | `Rp_t_pp` | `Rb_t_pp` | `Rp_t_pp - mean(Rp)` | `Rb_t_pp - mean(Rb)` | Product |
|---|---:|---:|---:|---:|---:|
| Day1 | 1.0 | 0.5 | 0.3333 | 0.1667 | 0.0556 |
| Day2 | -1.0 | -0.5 | -1.6667 | -0.8333 | 1.3889 |
| Day3 | 2.0 | 1.0 | 1.3333 | 0.6667 | 0.8889 |

Intermediate calculations:
- `mean(Rp) = (1.0 - 1.0 + 2.0)/3 = 0.6667`
- `mean(Rb) = (0.5 - 0.5 + 1.0)/3 = 0.3333`
- `Cov_pb = sum(product) / (n-1) = (0.0556 + 1.3889 + 0.8889)/2 = 1.1667`
- `Var_b = sum((Rb_t_pp - mean(Rb))^2)/(n-1) = (0.0278 + 0.6944 + 0.4444)/2 = 0.5833`
- `BETA = 1.1667 / 0.5833 = 2.0000`

Output mapping:
- `results[period].metrics.BETA.value = 2.0`
