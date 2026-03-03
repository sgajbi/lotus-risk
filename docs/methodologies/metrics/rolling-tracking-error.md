# Rolling Metric Methodology - Rolling Tracking Error

## Metric
- metric_id: ROLLING_TRACKING_ERROR

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio and benchmark returns.
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
1. Active decimal return: `a_t = r_portfolio_t - r_benchmark_t`.
2. Rolling sample std: `sigma_a_t(W)=std(a_{t-W+1..t},ddof=1)`.
3. Rolling tracking error: `RTE_t(W)=sigma_a_t(W)*sqrt(annualization_basis)`.

## Step-by-Step Computation
1. Align portfolio and benchmark return series in period scope.
2. Build active return vector.
3. Compute rolling sample std for each window.
4. Annualize each point and publish summaries/series.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.annualization_basis`

## Outputs
- `window_results[].metric_summaries.ROLLING_TRACKING_ERROR`

## Worked Example
- Window=3, active decimal returns `[0.001,-0.002,0.001]`.
- Sample std of active returns `0.001732`.
- Annualized TE point `0.001732*sqrt(252)=0.02749`.
- Repeat over all windows to produce rolling series.
- Summary fields are computed from valid rolling points only.