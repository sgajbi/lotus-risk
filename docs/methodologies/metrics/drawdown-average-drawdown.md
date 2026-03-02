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

## Methodology and Formulas
- AVERAGE_DRAWDOWN = mean(drawdown_t where drawdown_t<0)

## Configuration Options
- None

## Outputs
- summary.average_drawdown

## Worked Example
- Underwater values [-0.02,-0.04,-0.01] => -0.0233
