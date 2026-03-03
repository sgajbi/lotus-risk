# Rolling Metric Methodology - Rolling Maximum Drawdown

## Metric
- metric_id: ROLLING_MAX_DRAWDOWN

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
- `r_t`: decimal return sample in a rolling window.
- `W`: rolling window length.
- `W_k`: wealth path within one window.
- `DD_k`: drawdown path within one window.
- `RMDD_t(W) = min(DD_k)`.

## Methodology and Formulas
1. Within each window, build wealth `W_k=Π(1+r_k)`.
2. Drawdown `DD_k=W_k/cummax(W_k)-1`.
3. `RMDD_t=min(DD_k)`.

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
- `window_results[].metric_summaries.ROLLING_MAX_DRAWDOWN`
- `window_results[].metric_series[]`
- `results[period].quality_flags`

## Worked Example
Window returns `[0.05,-0.10,0.02]`.
| Window | Wealth Path | Drawdown Path | Value |
|---|---|---|---:|
| 1 | `[1.0500,0.9450,0.9639]` | `[0.0000,-0.1000,-0.0820]` | `-0.1000` |
Output mapping: `metric_summaries.ROLLING_MAX_DRAWDOWN.latest=-0.1000`.