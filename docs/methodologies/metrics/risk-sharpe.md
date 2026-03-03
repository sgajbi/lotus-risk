# Risk Metric Methodology - Sharpe Ratio

## Metric
- metric_id: SHARPE

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series in pp.
- Risk-free settings and annualization basis.

## Upstream Data Sources
- Stateless caller returns.
- Stateful lotus-performance returns.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. `rf_p=(1+rf_annual)^(1/annual_factor)-1` (or 0).
2. `mu_excess = mean(r_pp)/100 - rf_p`.
3. `sigma = std(r_pp,ddof=1)/100`.
4. `SHARPE=(mu_excess/sigma)*sqrt(annual_factor)`.

## Step-by-Step Computation
1. Resolve return sample and periodic RF.
2. Compute excess mean and sample volatility.
3. Fail on zero volatility.
4. Annualize ratio and emit metric.

## Configuration Options
- `options.risk_free_mode`
- `options.risk_free_annual_rate`
- `options.annualization_factor`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.SHARPE.value`
- `...details.error`

## Worked Example
- Mean return decimal `0.0005`, std decimal `0.01`.
- Annual RF `2.0%`, annualization `252` gives periodic RF `0.0000786`.
- Excess mean `0.0004214`.
- Sharpe `=(0.0004214/0.01)*sqrt(252)=0.669`.
- If std is zero, response returns `details.error=Zero volatility`.
