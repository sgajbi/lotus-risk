# Rolling Metric Methodology - Rolling Sharpe

## Metric
- metric_id: ROLLING_SHARPE

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series as dated percentage-point observations.
- Risk-free return series as dated percentage-point observations.
- One or more rolling window lengths.
- Annualization basis.
- Minimum-observation policy.
- Optional time-series emission flag.

## Upstream Data Sources
- Stateless mode: caller-provided `returns` and `risk_free_returns`.
- Stateful mode: `lotus-performance` provides portfolio returns and `lotus-core` provides risk-free reference returns through the governed rolling-metrics integration path.
- `lotus-risk` owns the rolling Sharpe calculation after dated return series are resolved. It does not source risk-free returns from Workbench, Gateway, manage, or local zero-rate assumptions.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- The engine converts portfolio and risk-free returns to decimal before rolling math:
  `r_decimal = r_pp / 100`.
- Excess returns are decimal differences.
- `ROLLING_SHARPE` output is a dimensionless annualized ratio.
- Response summary fields (`latest`, `average`, `minimum`, `maximum`, `p05`, `p50`, `p95`) use the same dimensionless ratio unit.

## Variable Dictionary
- `t`: aligned observation date.
- `Rp_t_pp`: portfolio return on date `t`, in percentage points.
- `Rf_t_pp`: risk-free return on date `t`, in percentage points.
- `Rp_t`: portfolio return on date `t`, as decimal (`Rp_t_pp / 100`).
- `Rf_t`: risk-free return on date `t`, as decimal (`Rf_t_pp / 100`).
- `x_t`: excess return on date `t`, as decimal (`Rp_t - Rf_t`).
- `W`: requested rolling window length.
- `min_obs`: minimum observations required for a window result.
- `AF`: annualization basis.
- `mu_x_t(W)`: arithmetic mean of excess returns inside the window ending on date `t`.
- `sigma_x_t(W)`: sample standard deviation of excess returns inside the window ending on date `t`, with `ddof=1`.
- `RS_t(W)`: rolling Sharpe ratio for the window ending on date `t`.

## Methodology and Formulas
1. Convert each portfolio and risk-free observation from pp to decimal:
   `Rp_t = Rp_t_pp / 100` and `Rf_t = Rf_t_pp / 100`.
2. Inner-align portfolio and risk-free series by date for the requested period.
3. Compute the excess return series:
   `x_t = Rp_t - Rf_t`.
4. Resolve minimum observations:
   - `min_obs = W` when `min_observations_policy = STRICT`;
   - `min_obs = 2` when `min_observations_policy = ALLOW_PARTIAL`.
5. For each date with at least `min_obs` observations in the rolling window, compute:
   - `mu_x_t(W) = mean(x_{t-W+1} ... x_t)`;
   - `sigma_x_t(W) = std(x_{t-W+1} ... x_t, ddof=1)`.
6. Annualize the mean/std ratio:
   `RS_t(W) = (mu_x_t(W) / sigma_x_t(W)) * sqrt(AF)`.
7. Replace infinite results with null before summaries are built.
8. Build summary statistics from computed, non-null `RS_t(W)` values only.

## Step-by-Step Computation
1. Resolve each requested period from `scope.as_of_date` and the period definition.
2. Filter portfolio and risk-free returns to the period.
3. Convert both filtered series from percentage points to decimal.
4. Inner-align the decimal series by date.
5. If no aligned observations remain, emit no computed metric values and record the risk-free dependency as `NO_ALIGNED_OBSERVATIONS`.
6. For each requested window length, compute rolling excess-return mean and sample standard deviation using `ddof=1`.
7. Annualize each non-zero-denominator point with `sqrt(rolling_options.annualization_basis)`.
8. Convert infinite values to null so zero excess-return volatility windows do not become misleading ratios.
9. Leave warm-up points as null until the configured minimum observation count is met.
10. Populate `metric_summaries.ROLLING_SHARPE` from non-null annualized ratios.
11. When `include_time_series=true`, emit `metric_series[].metric_values.ROLLING_SHARPE` for every point in the rolling result, with warm-up and zero-denominator points represented as null.

## Validation and Failure Behavior
- Stateless requests that include `ROLLING_SHARPE` without `risk_free_returns` fail request validation.
- Stateful requests require risk-free sourcing from `lotus-core`; unavailable upstream data fails closed with dependency details rather than falling back to a zero risk-free return.
- Fewer than two portfolio observations in the period returns period-level `error = "Insufficient data"` and no window results.
- Risk-free series supplied but with no aligned dates returns `risk_free_context.reason = "NO_ALIGNED_OBSERVATIONS"` and emits no computed Sharpe values for the metric.
- Window warm-up points are null until `min_obs` is met.
- Zero rolling excess-return standard deviation produces null metric points and quality flag `metric:ROLLING_SHARPE:zero_volatility_window`.
- Non-numeric return values are rejected by request-contract validation before engine math.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.annualization_basis`
- `rolling_options.min_observations_policy`
- `rolling_options.include_time_series`

## Outputs
- `window_results[].metric_summaries.ROLLING_SHARPE`
- `window_results[].metric_series[]`
- `results[period].quality_flags`

## Worked Example
Assume daily annualization (`AF = 252`), `STRICT` minimum observations, `W = 3`, and aligned return observations:

| Date | `Rp_t_pp` | `Rf_t_pp` | `Rp_t` | `Rf_t` | `x_t = Rp_t - Rf_t` |
| --- | ---: | ---: | ---: | ---: | ---: |
| Day 1 | `0.50` | `0.01` | `0.005` | `0.0001` | `0.0049` |
| Day 2 | `0.20` | `0.01` | `0.002` | `0.0001` | `0.0019` |
| Day 3 | `-0.10` | `0.01` | `-0.001` | `0.0001` | `-0.0011` |

Intermediate calculations for the first full window:

| Step | Value |
| --- | ---: |
| Excess mean | `(0.0057) / 3 = 0.0019` |
| Squared deviations sum | `0.0000180000` |
| Sample variance (`ddof=1`) | `0.0000090000` |
| `sigma_x_t(3)` | `0.0030000000` |
| Mean/std ratio | `0.6333333333` |
| Annualization multiplier | `sqrt(252) = 15.8745078664` |
| `RS_t(3)` | `10.0538549820` |

Output mapping:

- `results[period].window_results[0].metric_summaries.ROLLING_SHARPE.latest = 10.0538549820`
- when `include_time_series=true`, the Day 3 point is emitted as
  `metric_series[].metric_values.ROLLING_SHARPE = 10.0538549820`
