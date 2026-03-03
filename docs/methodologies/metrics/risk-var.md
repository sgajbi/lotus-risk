# Risk Metric Methodology - Value at Risk

## Metric
- metric_id: VAR

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series in pp.
- VaR method, confidence, horizon, ES flag.

## Upstream Data Sources
- Stateless caller.
- Stateful lotus-performance.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. `alpha=1-confidence`.
2. Historical VaR = percentile(alpha).
3. Gaussian VaR = mean + std*z(alpha).
4. Cornish-Fisher VaR = mean + std*z_cf(alpha,skew,kurtosis).
5. Scale horizon by `sqrt(horizon_days)`.
6. ES (optional) = mean(return <= VaR).

## Step-by-Step Computation
1. Compute one-day VaR by configured method.
2. Apply square-root-of-time scaling.
3. Optionally compute expected shortfall.
4. Emit value and details.

## Configuration Options
- `options.var.method`
- `options.var.confidence`
- `options.var.horizon_days`
- `options.var.include_expected_shortfall`

## Outputs
- `results[period].metrics.VAR.value`
- `...details.expected_shortfall`

## Worked Example
- Returns pp `[-2,-1,0,1,2]`, confidence `95%`.
- Historical one-day VaR at 5th percentile is `-1.8` pp.
- With horizon `4`, scaled VaR `=-1.8*sqrt(4)=-3.6` pp.
- If ES enabled, tail mean at or below VaR gives one-day ES (here near `-2.0` pp).
- Scaled ES for 4-day horizon is about `-4.0` pp.
