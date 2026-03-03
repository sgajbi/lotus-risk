# Rolling Metric Methodology - Rolling Volatility

## Metric
- metric_id: ROLLING_VOLATILITY

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
- `r_t`: decimal return sample.
- `W`: rolling window length.
- `sigma_t(W)`: rolling sample std at endpoint `t`.
- `AB`: annualization basis.
- `RV_t(W) = sigma_t(W)*sqrt(AB)`.

## Methodology and Formulas
1. `r_t=r_pp/100`.
2. `sigma_t(W)=std_W(r,ddof=1)`.
3. `RV_t=sigma_t(W)*sqrt(annualization_basis)`.

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
- `window_results[].metric_summaries.ROLLING_VOLATILITY`
- `window_results[].metric_series[]`
- `results[period].quality_flags`

## Worked Example
Window `3`, decimal returns `[0.010,-0.020,0.015]`.
| Window | Std | Annualization | Value |
|---|---:|---:|---:|
| 1 | `0.01893` | `sqrt(252)` | `0.3005` |
Output mapping: `window_results[].metric_summaries.ROLLING_VOLATILITY.latest=0.3005`.