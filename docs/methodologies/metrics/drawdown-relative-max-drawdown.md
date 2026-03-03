# Drawdown Methodology - Relative Max Drawdown vs Benchmark

## Metric
- metric_id: RELATIVE_MAX_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Benchmark returns

## Upstream Data Sources
- Stateless: caller benchmark_returns
- Stateful: lotus-performance benchmark_returns

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- active_t = portfolio_t - benchmark_t
- Compute drawdown path on active return wealth index

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: active_t = portfolio_t - benchmark_t
4. Apply: Compute drawdown path on active return wealth index
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- stateful benchmark_policy.include_benchmark
- stateful benchmark_policy.missing_benchmark_policy

## Outputs
- relative_to_benchmark.max_drawdown
- relative_to_benchmark.max_drawdown_peak_date
- relative_to_benchmark.max_drawdown_trough_date

## Worked Example
Given:
- Active returns(dec): [0.01,-0.03,0.005] => relative max drawdown around -0.03
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

