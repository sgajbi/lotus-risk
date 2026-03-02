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

## Methodology and Formulas
- active_t = portfolio_t - benchmark_t
- Compute drawdown path on active return wealth index

## Configuration Options
- stateful benchmark_policy.include_benchmark
- stateful benchmark_policy.missing_benchmark_policy

## Outputs
- relative_to_benchmark.max_drawdown
- relative_to_benchmark.max_drawdown_peak_date
- relative_to_benchmark.max_drawdown_trough_date

## Worked Example
- Active returns(dec): [0.01,-0.03,0.005] => relative max drawdown around -0.03
