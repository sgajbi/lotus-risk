# Risk Metric Methodology - Information Ratio

## Metric
- metric_id: INFORMATION_RATIO

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Benchmark returns

## Upstream Data Sources
- Stateless: caller
- Stateful: lotus-performance

## Methodology and Formulas
- active_t = Rp_t - Rb_t
- IR = (mean(active_t)/std(active_t))*sqrt(annual_factor)

## Configuration Options
- options.frequency
- options.annualization_factor

## Outputs
- results[period].metrics.INFORMATION_RATIO.value

## Worked Example
- Active [%]: [0.2,0.1,-0.1,0.0] => IR ~= 6.15 (annual_factor=252)
