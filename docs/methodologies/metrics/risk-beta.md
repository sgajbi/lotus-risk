# Risk Metric Methodology - Beta

## Metric
- metric_id: BETA

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Benchmark returns (date-aligned)

## Upstream Data Sources
- Stateless: caller benchmark_returns[]
- Stateful: lotus-performance benchmark_returns

## Methodology and Formulas
- Beta = Cov(Rp,Rb)/Var(Rb), ddof=1
- Inner date join before calculation

## Configuration Options
- options.frequency
- options.use_log_returns

## Outputs
- results[period].metrics.BETA.value
- details.error when benchmark variance is zero

## Worked Example
- Portfolio approximately 2x benchmark => beta ~= 2.0
