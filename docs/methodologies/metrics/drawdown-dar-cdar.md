# Drawdown Methodology - Drawdown-at-Risk and CDaR

## Metric
- metric_id: DRAWDOWN_AT_RISK_AND_CDAR

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Episode depth distribution

## Upstream Data Sources
- Episode extraction from drawdown path

## Methodology and Formulas
- DaR_alpha = quantile(depths,1-alpha)
- CDaR_alpha = mean(depth <= DaR_alpha)

## Configuration Options
- analysis_options.cdar_alpha (0.90,0.95,0.99)

## Outputs
- summary.drawdown_at_risk_95
- summary.conditional_drawdown_at_risk_95

## Worked Example
- Depths [-0.03,-0.08,-0.12,-0.05], alpha=0.95 => DaR/CDaR from lower tail
