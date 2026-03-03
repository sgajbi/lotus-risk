# Rolling Metric Methodology - Rolling Beta

## Metric
- metric_id: ROLLING_BETA

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series.
- Additional required series by metric (benchmark/risk-free where applicable).
- Window lengths and annualization basis.

## Upstream Data Sources
- Stateless caller input or stateful integrated return series.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when required: `r_decimal = r_pp / 100`.
- Output units are metric-specific (ratio, annualized pp, decimal drawdown, or HHI scale).

## Variable Dictionary
- `r_port_t`, `r_bench_t`: decimal return series.
- `W`: rolling window length.
- `cov_t(W)`: rolling covariance.
- `var_b_t(W)`: rolling benchmark variance.
- `RBETA_t(W) = cov_t/var_b_t`.

## Methodology and Formulas
1. `cov_t=cov_W(Rp,Rb)`.
2. `var_t=var_W(Rb)`.
3. `ROLLING_BETA_t=cov_t/var_t`.

## Step-by-Step Computation
1. Resolve period and filter returns.
2. Align required series by date for the metric.
3. Compute rolling metric pointwise for each requested window.
4. Build summaries and optional metric series.

## Validation and Failure Behavior
- Insufficient window observations produce null points until min periods are met.
- Alignment-empty joins produce empty or null series with quality flags.
- Zero denominators produce null points and metric-specific flags.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.annualization_basis`
- `rolling_options.min_observations_policy`
- `rolling_options.include_time_series`

## Outputs
- `window_results[].metric_summaries.ROLLING_BETA`
- `window_results[].metric_series[]`
- `results[period].quality_flags`

## Worked Example
Window benchmark `[0.01,-0.02,0.015]`, portfolio `[0.015,-0.03,0.0225]`.
| Window | Covariance | Benchmark Variance | Value |
|---|---:|---:|---:|
| 1 | `0.000525` | `0.000350` | `1.5` |
Output mapping: `metric_summaries.ROLLING_BETA.latest=1.5`.