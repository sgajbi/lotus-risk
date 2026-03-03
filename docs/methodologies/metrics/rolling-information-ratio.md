# Rolling Metric Methodology - Rolling Information Ratio

## Metric
- metric_id: ROLLING_INFORMATION_RATIO

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
1. Active return vector: `a_t = r_portfolio_t - r_benchmark_t`.
2. Rolling active mean: `mu_a_t(W)=mean(a_{t-W+1..t})`.
3. Rolling active std: `sigma_a_t(W)=std(a_{t-W+1..t},ddof=1)`.
4. Rolling information ratio: `RIR_t(W)=(mu_a_t/sigma_a_t)*sqrt(annualization_basis)`.

## Step-by-Step Computation
1. Align series and compute active return stream.
2. Compute rolling active mean and std per window length.
3. Compute ratio and annualize by configured basis.
4. Null zero-std points and emit quality flags.
5. Return summary distribution and optional full series.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.annualization_basis`

## Outputs
- `window_results[].metric_summaries.ROLLING_INFORMATION_RATIO`
- `quality_flags`

## Worked Example
- Window=3, active decimal returns `[0.002,0.001,-0.001]`.
- Rolling mean `0.000667` and sample std `0.001528`.
- Point IR `=(0.000667/0.001528)*sqrt(252)=6.928`.
- If rolling std is zero, value is null and quality flag is emitted.
- Summary aggregates valid window points.