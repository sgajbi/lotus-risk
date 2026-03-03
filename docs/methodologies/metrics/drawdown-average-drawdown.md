# Drawdown Methodology - Average Drawdown

## Metric
- metric_id: AVERAGE_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Underwater drawdown observations

## Upstream Data Sources
- Derived from return series

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- AVERAGE_DRAWDOWN = mean(drawdown_t where drawdown_t<0)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: AVERAGE_DRAWDOWN = mean(drawdown_t where drawdown_t<0)
4. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- None

## Outputs
- summary.average_drawdown

## Worked Example
Given:
- Underwater values [-0.02,-0.04,-0.01] => -0.0233
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

