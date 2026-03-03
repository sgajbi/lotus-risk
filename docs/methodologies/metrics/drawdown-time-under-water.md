# Drawdown Methodology - Time Under Water

## Metric
- metric_id: TIME_UNDER_WATER_DAYS

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Drawdown series

## Upstream Data Sources
- Derived from return series

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- time_under_water_days = count(drawdown_t < 0)
- Episode timing metrics are duration-unit aware

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: time_under_water_days = count(drawdown_t < 0)
4. Apply: Episode timing metrics are duration-unit aware
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- analysis_options.duration_unit = BUSINESS_DAYS|CALENDAR_DAYS

## Outputs
- summary.time_under_water_days
- episodes.days_to_trough
- episodes.days_to_recovery
- episodes.total_days

## Worked Example
Given:
- Drawdown [0,-0.02,-0.01,0] => time under water = 2
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

