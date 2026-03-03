# Rolling Metric Methodology - Rolling Volatility

## Metric
- metric_id: ROLLING_VOLATILITY

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- window_lengths[]

## Upstream Data Sources
- Stateless: caller returns[]
- Stateful: lotus-performance portfolio_returns

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- Convert returns to decimal
- rolling_std(window,ddof=1)*sqrt(annualization_basis)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: Convert returns to decimal
4. Apply: rolling_std(window,ddof=1)*sqrt(annualization_basis)
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- rolling_options.window_lengths
- rolling_options.annualization_basis
- rolling_options.min_observations_policy

## Outputs
- window_results[].metric_summaries.ROLLING_VOLATILITY
- optional metric_series

## Worked Example
Given:
- Window=3, returns(dec) [0.01,-0.02,0.015] => 0.3005 annualized
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

