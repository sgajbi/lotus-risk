# Rolling Metric Methodology - Rolling Max Drawdown

## Metric
- metric_id: ROLLING_MAX_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/rolling-metrics
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- window_lengths[]

## Upstream Data Sources
- Stateless: caller
- Stateful: lotus-performance

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- For each rolling window: wealth=Π(1+r)
- drawdown=wealth/cummax(wealth)-1
- window metric=min(drawdown)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: For each rolling window: wealth=Π(1+r)
4. Apply: drawdown=wealth/cummax(wealth)-1
5. Apply: window metric=min(drawdown)
6. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- window_lengths
- min_observations_policy

## Outputs
- window_results[].metric_summaries.ROLLING_MAX_DRAWDOWN

## Worked Example
Given:
- Window returns [0.02,-0.03,0.01] => rolling max drawdown ~ -0.03
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

