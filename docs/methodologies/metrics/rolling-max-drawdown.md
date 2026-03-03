# Rolling Metric Methodology - Rolling Maximum Drawdown

## Metric
- metric_id: ROLLING_MAX_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series.
- Window lengths.

## Upstream Data Sources
- Stateless caller.
- Stateful lotus-performance.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. For each trailing window, convert returns to decimal and build wealth path `W_k=Π(1+r_k)`.
2. Build window running peak `P_k=cummax(W_k)`.
3. Build window drawdown `DD_k=W_k/P_k-1`.
4. Rolling max drawdown point: `RMDD_t(W)=min(DD_k)`.

## Step-by-Step Computation
1. For each date `t`, extract trailing `W`-length window.
2. Compute wealth, running peak, and drawdown inside that window.
3. Record minimum drawdown as rolling point.
4. Repeat for all dates and produce summary stats.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.min_observations_policy`

## Outputs
- `window_results[].metric_summaries.ROLLING_MAX_DRAWDOWN`

## Worked Example
- Window decimal returns `[0.05,-0.10,0.02]`.
- Window wealth `[1.0500,0.9450,0.9639]` and running peak `[1.0500,1.0500,1.0500]`.
- Window drawdown `[0.0000,-0.1000,-0.0820]`.
- Rolling max drawdown point = `-0.1000`.
- Rolling summary combines all window points for period.