# Drawdown Methodology - Ulcer Index

## Metric
- metric_id: ULCER_INDEX

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Full drawdown path

## Upstream Data Sources
- Derived from return series

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- ULCER_INDEX = sqrt(mean(drawdown_t^2))

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: ULCER_INDEX = sqrt(mean(drawdown_t^2))
4. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- None

## Outputs
- summary.ulcer_index

## Worked Example
Given:
- Drawdown [0,-0.02,-0.04] => ulcer index=0.0258
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

