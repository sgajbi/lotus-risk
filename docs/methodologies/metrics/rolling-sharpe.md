# Rolling Metric Methodology - Rolling Sharpe

## Metric
- metric_id: ROLLING_SHARPE

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio and risk-free return series.
- Window lengths and annualization basis.

## Upstream Data Sources
- Stateless caller.
- Stateful lotus-performance/core integrations.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Excess return vector vs risk-free: `x_t = r_portfolio_t - r_rf_t`.
2. Rolling mean: `mu_x_t(W)=mean(x_{t-W+1..t})`.
3. Rolling std: `sigma_x_t(W)=std(x_{t-W+1..t},ddof=1)`.
4. Rolling Sharpe: `RS_t(W)=(mu_x_t/sigma_x_t)*sqrt(annualization_basis)`.

## Step-by-Step Computation
1. Inner-align portfolio and risk-free return series.
2. Compute excess return stream.
3. Compute rolling mean/std for each window.
4. Compute annualized Sharpe and flag zero-std windows.
5. Build summaries and optional metric series.

## Configuration Options
- `rolling_options.window_lengths`
- `rolling_options.annualization_basis`

## Outputs
- `window_results[].metric_summaries.ROLLING_SHARPE`
- `results[period].quality_flags`

## Worked Example
- Window=3, excess decimal returns `[0.004,0.001,-0.002]`.
- Rolling mean `0.001000`, sample std `0.003000`.
- Point Sharpe `=(0.001/0.003)*sqrt(252)=5.291`.
- If std is zero, point is null and flagged.
- Summary reports distribution of rolling Sharpe points.