# Rolling Metric Methodology - Rolling Volatility

## Metric
- metric_id: ROLLING_VOLATILITY

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns.
- Window lengths.
- Annualization basis.

## Upstream Data Sources
- Stateless caller.
- Stateful lotus-performance.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Convert returns to decimal: `r_t = r_pp/100`.
2. For each window size `W`, rolling sample std: `sigma_t(W)=std(r_{t-W+1..t},ddof=1)`.
3. Annualized rolling volatility: `RV_t(W)=sigma_t(W)*sqrt(annualization_basis)`.

## Step-by-Step Computation
1. Resolve period and decimal return series.
2. For each window length, run rolling sample std with configured minimum observations.
3. Annualize each rolling point.
4. Build summary statistics and optional point-wise series output.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.annualization_basis`
- `rolling_options.min_observations_policy`

## Outputs
- `window_results[].metric_summaries.ROLLING_VOLATILITY`
- `window_results[].metric_series[]`

## Worked Example
- Window=3, decimal returns `[0.010,-0.020,0.015]`.
- Sample std `0.01893`.
- Annualization basis `252`.
- Rolling volatility point `0.01893*sqrt(252)=0.3005`.
- Window summary reports latest/avg/min/max/percentiles across all points.