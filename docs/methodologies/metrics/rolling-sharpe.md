# Rolling Metric Methodology - Rolling Sharpe

## Metric
- metric_id: ROLLING_SHARPE

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
- `r_port_t`, `r_rf_t`: decimal portfolio and risk-free returns.
- `x_t = r_port_t - r_rf_t`: excess return.
- `W`: rolling window length.
- `mu_t(W)`, `sigma_t(W)`: rolling excess mean/std.
- `RS_t(W) = (mu_t/sigma_t)*sqrt(AB)`.

## Methodology and Formulas
1. `x_t=r_port_t-r_rf_t`.
2. `mu_t=mean_W(x_t)`, `sigma_t=std_W(x_t,ddof=1)`.
3. `RS_t=(mu_t/sigma_t)*sqrt(annualization_basis)`.

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
- `window_results[].metric_summaries.ROLLING_SHARPE`
- `window_results[].metric_series[]`
- `results[period].quality_flags`

## Worked Example
Window `3`, excess returns `[0.004,0.001,-0.002]`.
| Window | Mean | Std | Annualization | Value |
|---|---:|---:|---:|---:|
| 1 | `0.0010` | `0.0030` | `sqrt(252)` | `5.291` |
Output mapping: latest value appears in `metric_summaries.ROLLING_SHARPE.latest`.