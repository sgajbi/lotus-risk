# Rolling Metric Methodology - Rolling Beta

## Metric
- metric_id: ROLLING_BETA

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Benchmark returns

## Upstream Data Sources
- Stateless: caller benchmark_returns[]
- Stateful: lotus-performance benchmark_returns

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- rolling_cov(portfolio,benchmark)/rolling_var(benchmark)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: rolling_cov(portfolio,benchmark)/rolling_var(benchmark)
4. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- window_lengths
- min_observations_policy
- alignment_policy INNER_JOIN

## Outputs
- window_results[].metric_summaries.ROLLING_BETA
- quality flag metric:ROLLING_BETA:benchmark_variance_zero

## Worked Example
Given:
- Portfolio ~1.5x benchmark over window => rolling beta ~1.5
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

