# Risk Metric Methodology - Value at Risk

## Metric
- metric_id: VAR

## Endpoint and Mode Coverage
- endpoint: `/analytics/risk/calculate`
- supported_modes: stateless, stateful
- source product: `RiskMetricsReport:v1`

## Inputs
- Portfolio return observations in percentage points.
- Request periods resolved by the risk calculation contract.
- `options.frequency` for optional return compounding before metric calculation.
- `options.use_log_returns` for optional log-return transformation after frequency compounding.
- `options.var.method`: `HISTORICAL`, `GAUSSIAN`, or `CORNISH_FISHER`.
- `options.var.confidence`: confidence level, strictly between `0` and `1`.
- `options.var.horizon_days`: positive integer horizon for square-root-of-time scaling.
- `options.var.include_expected_shortfall`: whether to emit expected shortfall details.

## Upstream Data Sources
- Stateless callers provide return observations directly in the request.
- Stateful mode resolves return observations from `lotus-performance`.
- No benchmark dependency is required for `VAR`.
- No risk-free dependency is required for `VAR`.

## Unit Conventions
- Return inputs are percentage points: `1.0` means `+1%`.
- Frequency resampling compounds percentage-point returns before metric calculation:
  `r_resampled_pp = ((product(1 + r_raw_pp / 100)) - 1) * 100`.
- When log returns are enabled, the transformed return remains in percentage points:
  `r_log_pp = ln(1 + r_pp / 100) * 100`.
- `metrics.VAR.value`, `details.base_var`, `details.base_expected_shortfall`, and
  `details.expected_shortfall` are signed return thresholds in percentage points.
- Negative values indicate lower-tail loss thresholds. Positive values can occur when the selected
  period's lower-tail return threshold remains positive.

## Variable Dictionary
- `t`: observation index in chronological order.
- `r_raw_t_pp`: raw portfolio return at `t`, in percentage points.
- `r_used_t_pp`: portfolio return used by the metric after frequency compounding and optional
  log-return transformation, in percentage points.
- `N`: count of portfolio observations used by the metric.
- `c`: confidence level from `options.var.confidence`.
- `alpha`: tail probability, `1 - c`.
- `z_alpha`: standard-normal quantile at `alpha`.
- `mu_pp`: arithmetic mean of `r_used_t_pp`.
- `sigma_pp`: sample standard deviation of `r_used_t_pp` with `ddof=1`.
- `S`: sample skewness from `pandas.Series.skew()`.
- `K`: sample excess kurtosis from `pandas.Series.kurt()`.
- `z_cf`: Cornish-Fisher adjusted quantile.
- `VaR_base_pp`: one-day VaR before horizon scaling, in percentage points.
- `h`: horizon days from `options.var.horizon_days`.
- `scale_h`: square-root-of-time horizon scale factor, `sqrt(h)`.
- `VaR_h_pp`: horizon-scaled VaR, in percentage points.
- `T`: expected-shortfall tail set, `{r_used_t_pp | r_used_t_pp <= VaR_base_pp}`.
- `ES_base_pp`: one-day expected shortfall before horizon scaling, in percentage points.
- `ES_h_pp`: horizon-scaled expected shortfall, in percentage points.

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
5. Compute tail probability:
   `alpha = 1 - c`.
6. Compute one-day base VaR using the selected method:
   - `HISTORICAL`: `VaR_base_pp = percentile(r_used_pp, alpha * 100)` using NumPy percentile
     interpolation.
   - `GAUSSIAN`: `VaR_base_pp = mu_pp + sigma_pp * z_alpha`.
   - `CORNISH_FISHER`:
     `z_cf = z_alpha + ((z_alpha^2 - 1) * S) / 6 + ((z_alpha^3 - 3 * z_alpha) * K) / 24 - ((2 * z_alpha^3 - 5 * z_alpha) * S^2) / 36`;
     `VaR_base_pp = mu_pp + sigma_pp * z_cf`.
7. Compute horizon scale:
   `scale_h = sqrt(h)`.
8. Compute reported VaR:
   `VaR_h_pp = VaR_base_pp * scale_h`.
9. When expected shortfall is enabled, compute:
   - `T = {r_used_t_pp | r_used_t_pp <= VaR_base_pp}`;
   - `ES_base_pp = mean(T)` when `T` is non-empty;
   - `ES_base_pp = VaR_base_pp` when `T` is empty;
   - `ES_h_pp = ES_base_pp * scale_h`.

## Step-by-Step Computation
1. Resolve the period start/end dates from the request period and portfolio open date.
2. Select portfolio returns within the resolved period.
3. Compound returns to the requested frequency when frequency is not `DAILY`.
4. Apply optional log-return transformation.
5. Require at least two observations after filtering, frequency compounding, and optional
   transformation.
6. Read VaR method, confidence, horizon days, and expected-shortfall flag.
7. Compute one-day `base_var` through the selected method.
8. Compute `horizon_scale_factor = sqrt(horizon_days)`.
9. Compute `metrics.VAR.value = base_var * horizon_scale_factor`.
10. Count tail observations where `r_used_t_pp <= base_var`.
11. Populate core details: method, confidence, tail probability, base horizon, horizon days,
    horizon scale method, horizon scale factor, expected-shortfall flag, base VaR, observation
    count, and tail observation count.
12. When expected shortfall is enabled, compute and populate base expected shortfall,
    expected-shortfall observation count, and horizon-scaled expected shortfall.

## Validation and Failure Behavior
- Fewer than two portfolio observations after period filtering, frequency compounding, and optional
  transformation return `metrics.VAR.value = null` with `details.error = "Insufficient data"`.
- Unsupported methods are rejected by request validation; the engine also fails closed with
  `details.error = "Unsupported VaR method: <method>"` if an invalid method reaches calculation.
- `options.var.confidence` must be greater than `0` and less than `1` by request-contract
  validation.
- `options.var.horizon_days` must be positive by request-contract validation.
- Non-numeric return values are rejected by request validation before engine math.
- Invalid log-return inputs that make `ln(1 + r_pp / 100)` undefined are rejected by request
  validation or produce invalid numeric results before supportable output is claimed.
- Expected-shortfall tail-set empty posture is deterministic: `base_expected_shortfall` falls back
  to `base_var` before horizon scaling.
- No benchmark dependency is required for `VAR`.
- No risk-free dependency is required for `VAR`.
- No annualization factor is used for `VAR`; horizon scaling is controlled only by
  `options.var.horizon_days`.

## Configuration Options
- `options.frequency`
- `options.use_log_returns`
- `options.var.method`
- `options.var.confidence`
- `options.var.horizon_days`
- `options.var.include_expected_shortfall`

## Outputs
- `results[period].metrics.VAR.value`
- `results[period].metrics.VAR.details.method`
- `results[period].metrics.VAR.details.confidence`
- `results[period].metrics.VAR.details.tail_probability`
- `results[period].metrics.VAR.details.base_horizon_days`
- `results[period].metrics.VAR.details.horizon_days`
- `results[period].metrics.VAR.details.horizon_scale_method`
- `results[period].metrics.VAR.details.horizon_scale_factor`
- `results[period].metrics.VAR.details.include_expected_shortfall`
- `results[period].metrics.VAR.details.base_var`
- `results[period].metrics.VAR.details.observation_count`
- `results[period].metrics.VAR.details.tail_observation_count`
- `results[period].metrics.VAR.details.base_expected_shortfall`
- `results[period].metrics.VAR.details.expected_shortfall_observation_count`
- `results[period].metrics.VAR.details.expected_shortfall`
- `results[period].metrics.VAR.details.error`

Consumer guidance:
- Display VaR as a signed return threshold unless a downstream UI explicitly transforms it into a
  positive loss convention.
- Do not relabel positive VaR as a loss; explain that the selected period's lower-tail return
  threshold is positive.
- Downstream consumers must preserve source-owned signed VaR and expected-shortfall values rather
  than recalculating or changing sign conventions locally.

## Worked Example
Assume:
- method: `HISTORICAL`
- confidence: `0.95`
- horizon days: `h = 4`
- expected shortfall: enabled
- returns (pp): `[-2.00, -1.00, 0.00, 1.00, 2.00]`
- `use_log_returns = false`

| Sorted index | `r_used_t_pp` |
| ---: | ---: |
| 0 | -2.00 |
| 1 | -1.00 |
| 2 | 0.00 |
| 3 | 1.00 |
| 4 | 2.00 |

Intermediate calculations:
- `N = 5`
- `alpha = 1 - 0.95 = 0.05`
- NumPy percentile position for `5%` lies between sorted index `0` and `1` at `20%` weight.
- `VaR_base_pp = -2.00 + 0.20 * (-1.00 - (-2.00)) = -1.8000000000`
- `scale_h = sqrt(4) = 2.0000000000`
- `VaR_h_pp = -1.8000000000 * 2.0000000000 = -3.6000000000`
- `T = {r_used_t_pp <= -1.8000000000} = [-2.00]`
- `ES_base_pp = mean([-2.00]) = -2.0000000000`
- `ES_h_pp = -2.0000000000 * 2.0000000000 = -4.0000000000`

Output mapping:
- `results[period].metrics.VAR.value = -3.6000000000`
- `results[period].metrics.VAR.details.method = "HISTORICAL"`
- `results[period].metrics.VAR.details.confidence = 0.9500000000`
- `results[period].metrics.VAR.details.tail_probability = 0.0500000000`
- `results[period].metrics.VAR.details.base_horizon_days = 1`
- `results[period].metrics.VAR.details.horizon_days = 4`
- `results[period].metrics.VAR.details.horizon_scale_method = "SQRT_TIME"`
- `results[period].metrics.VAR.details.horizon_scale_factor = 2.0000000000`
- `results[period].metrics.VAR.details.include_expected_shortfall = true`
- `results[period].metrics.VAR.details.base_var = -1.8000000000`
- `results[period].metrics.VAR.details.observation_count = 5`
- `results[period].metrics.VAR.details.tail_observation_count = 1`
- `results[period].metrics.VAR.details.base_expected_shortfall = -2.0000000000`
- `results[period].metrics.VAR.details.expected_shortfall_observation_count = 1`
- `results[period].metrics.VAR.details.expected_shortfall = -4.0000000000`
