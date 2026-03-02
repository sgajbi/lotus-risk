# Risk Metric Methodology - Tracking Error

## Metric
- metric_id: TRACKING_ERROR

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
- TE = std(active_t,ddof=1)*sqrt(annual_factor)

## Configuration Options
- options.frequency
- options.annualization_factor

## Outputs
- results[period].metrics.TRACKING_ERROR.value

## Worked Example
- Active [%]: [0.1,-0.2,0.1], annual_factor=252 => TE ~= 2.75
