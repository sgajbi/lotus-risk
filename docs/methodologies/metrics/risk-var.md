# Risk Metric Methodology - Value at Risk

## Metric
- metric_id: VAR

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series in pp.
- VaR method, confidence, horizon, ES flag.

## Upstream Data Sources
- Stateless caller.
- Stateful lotus-performance.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Variable Dictionary
- `r_t_pp`: return observation in percentage points (post-transform if log mode is used).
- `n`: number of observations in the period sample.
- `c`: confidence level (`options.var.confidence`).
- `alpha`: tail probability (`alpha = 1 - c`).
- `z_alpha`: normal quantile at `alpha`.
- `mu_pp`: sample mean return in pp.
- `sigma_pp`: sample standard deviation in pp (`ddof=1`).
- `S`: sample skewness (pandas `Series.skew()`).
- `K`: sample excess kurtosis (pandas `Series.kurt()`).
- `z_cf`: Cornish-Fisher adjusted quantile.
- `VaR_1d_pp`: one-day VaR in pp before horizon scaling.
- `h`: horizon days (`options.var.horizon_days`).
- `VaR_h_pp`: horizon-scaled VaR in pp.
- `ES_1d_pp`: one-day expected shortfall in pp.
- `ES_h_pp`: horizon-scaled expected shortfall in pp.

## Methodology and Formulas
1. Optional return transform:
- if `use_log_returns=false`: use raw pp returns
- if `use_log_returns=true`: transform each return as `ln(1 + r_pp/100) * 100`
2. Tail probability:
`alpha = 1 - confidence`.
3. One-day VaR by method:
- `HISTORICAL`: `VaR_1d_pp = percentile(sample, alpha*100)` (NumPy linear interpolation).
- `GAUSSIAN`: `VaR_1d_pp = mu_pp + sigma_pp * z_alpha`.
- `CORNISH_FISHER`:
  - `z_cf = z_alpha + ((z_alpha^2-1)S)/6 + ((z_alpha^3-3z_alpha)K)/24 - ((2z_alpha^3-5z_alpha)S^2)/36`
  - `VaR_1d_pp = mu_pp + sigma_pp * z_cf`
4. Horizon scaling:
`VaR_h_pp = VaR_1d_pp * sqrt(h)`.
5. Optional expected shortfall:
- tail set `T = {r_t_pp | r_t_pp <= VaR_1d_pp}`
- `ES_1d_pp = mean(T)` if `T` non-empty, else `VaR_1d_pp`
- `ES_h_pp = ES_1d_pp * sqrt(h)`

## Step-by-Step Computation
1. Resolve period and filter return observations to the selected window.
2. Apply frequency resampling and optional log-return transform.
3. Validate minimum sample size (`>=2`) for stable distribution estimates.
4. Read VaR configuration (`method`, `confidence`, `horizon_days`, ES flag).
5. Compute one-day VaR using the selected method.
6. Apply horizon scaling `sqrt(horizon_days)` to obtain reported VaR.
7. If ES is enabled, compute one-day ES from tail at one-day cutoff, then horizon-scale ES.
8. Emit `metrics.VAR.value` and optional `details.expected_shortfall`.

## Validation and Failure Behavior
- Fewer than 2 observations: `details.error = "Insufficient data"`.
- Unsupported method: `details.error = "Unsupported VaR method: <method>"`.
- Non-numeric return values: rejected by request-contract validation before engine math.
- ES tail set empty is handled deterministically by falling back to one-day VaR before scaling.
- `horizon_days` must be positive by request-contract validation.

## Configuration Options
- `options.var.method`
- `options.var.confidence`
- `options.var.horizon_days`
- `options.var.include_expected_shortfall`

## Outputs
- `results[period].metrics.VAR.value`
- `results[period].metrics.VAR.details.expected_shortfall` (when enabled)
- `results[period].metrics.VAR.details.error`

## Worked Example
Assume method `HISTORICAL`, confidence `0.95`, horizon `h=4`, ES enabled.
Sample returns (pp): `[-2, -1, 0, 1, 2]`

| Sorted Index | Return (pp) |
|---:|---:|
| 0 | -2.0 |
| 1 | -1.0 |
| 2 | 0.0 |
| 3 | 1.0 |
| 4 | 2.0 |

Intermediate calculations:
- `alpha = 1 - 0.95 = 0.05`
- One-day VaR percentile position (`numpy percentile`, linear): between index 0 and 1 at 20% weight
- `VaR_1d_pp = -2.0 + 0.2 * (-1.0 - (-2.0)) = -1.8`
- `VaR_h_pp = -1.8 * sqrt(4) = -3.6`
- Tail set for ES at one-day cutoff: `T = {r <= -1.8} = [-2.0]`
- `ES_1d_pp = mean([-2.0]) = -2.0`
- `ES_h_pp = -2.0 * sqrt(4) = -4.0`

Output mapping:
- `results[period].metrics.VAR.value = -3.6`
- `results[period].metrics.VAR.details.expected_shortfall = -4.0`
