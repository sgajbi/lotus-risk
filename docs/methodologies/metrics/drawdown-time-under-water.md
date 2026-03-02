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

## Methodology and Formulas
- time_under_water_days = count(drawdown_t < 0)
- Episode timing metrics are duration-unit aware

## Configuration Options
- analysis_options.duration_unit = BUSINESS_DAYS|CALENDAR_DAYS

## Outputs
- summary.time_under_water_days
- episodes.days_to_trough
- episodes.days_to_recovery
- episodes.total_days

## Worked Example
- Drawdown [0,-0.02,-0.01,0] => time under water = 2
