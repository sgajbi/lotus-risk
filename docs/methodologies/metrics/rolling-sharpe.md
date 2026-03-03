# Rolling Metric Methodology - Rolling Sharpe

## Metric
- metric_id: ROLLING_SHARPE

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Risk-free returns

## Upstream Data Sources
- Stateless: caller risk_free_returns[]
- Stateful: lotus-performance risk_free_returns

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- active_t = portfolio_t - risk_free_t
- rolling_mean(active)/rolling_std(active)*sqrt(annualization_basis)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: active_t = portfolio_t - risk_free_t
4. Apply: rolling_mean(active)/rolling_std(active)*sqrt(annualization_basis)
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- window_lengths
- annualization_basis
- alignment_policy INNER_JOIN

## Outputs
- window_results[].metric_summaries.ROLLING_SHARPE
- quality flag metric:ROLLING_SHARPE:zero_volatility_window

## Worked Example
Given:
- Window=3 active(dec) [0.001,0.002,-0.001] => rolling Sharpe ~= 6.93
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

