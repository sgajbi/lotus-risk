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

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- DaR_alpha = quantile(depths,1-alpha)
- CDaR_alpha = mean(depth <= DaR_alpha)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: DaR_alpha = quantile(depths,1-alpha)
4. Apply: CDaR_alpha = mean(depth <= DaR_alpha)
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- analysis_options.cdar_alpha (0.90,0.95,0.99)

## Outputs
- summary.drawdown_at_risk_95
- summary.conditional_drawdown_at_risk_95

## Worked Example
Given:
- Depths [-0.03,-0.08,-0.12,-0.05], alpha=0.95 => DaR/CDaR from lower tail
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

