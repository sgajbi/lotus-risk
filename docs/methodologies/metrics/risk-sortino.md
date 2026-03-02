# Risk Metric Methodology - Sortino Ratio

## Metric
- metric_id: SORTINO

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series
- MAR annual rate

## Upstream Data Sources
- Stateless: caller returns[]
- Stateful: lotus-performance portfolio_returns

## Methodology and Formulas
- periodic_mar = (1+mar_annual_rate)^(1/annual_factor)-1
- downside = r_t-periodic_mar where downside<0
- Sortino = ((mean(r)-periodic_mar)/sqrt(mean(downside^2)))*sqrt(annual_factor)

## Configuration Options
- options.mar_annual_rate
- options.frequency
- options.annualization_factor

## Outputs
- results[period].metrics.SORTINO.value
- details.error when downside observations missing

## Worked Example
- Returns(dec): [0.01,-0.02,0.005], MAR=0
- Sortino ~= -1.32
