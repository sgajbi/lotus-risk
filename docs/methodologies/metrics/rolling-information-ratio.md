# Rolling Metric Methodology - Rolling Information Ratio

## Metric
- metric_id: ROLLING_INFORMATION_RATIO

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Benchmark returns

## Upstream Data Sources
- Stateless: caller
- Stateful: lotus-performance

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- active_t = Rp_t - Rb_t
- rolling_mean(active)/rolling_std(active)*sqrt(annualization_basis)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: active_t = Rp_t - Rb_t
4. Apply: rolling_mean(active)/rolling_std(active)*sqrt(annualization_basis)
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- window_lengths
- annualization_basis

## Outputs
- window_results[].metric_summaries.ROLLING_INFORMATION_RATIO
- quality flag metric:ROLLING_INFORMATION_RATIO:zero_tracking_error_window

## Worked Example
Given:
- Computed per rolling window on active return stream
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

