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

## Methodology and Formulas
- ULCER_INDEX = sqrt(mean(drawdown_t^2))

## Configuration Options
- None

## Outputs
- summary.ulcer_index

## Worked Example
- Drawdown [0,-0.02,-0.04] => ulcer index=0.0258
