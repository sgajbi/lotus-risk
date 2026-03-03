# Risk Metric Methodology - Volatility

## Metric
- metric_id: VOLATILITY

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return observations for the resolved period (minimum 2).
- Annualization basis from frequency or explicit override.
- Optional log-return transform flag.

## Upstream Data Sources
- Stateless: caller `returns[]`.
- Stateful: lotus-performance return series.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. If enabled: `r_t = ln(1+r_t/100)*100`.
2. `sigma_pp = std(r_t, ddof=1)`.
3. `VOLATILITY = sigma_pp * sqrt(annualization_factor)`.

## Step-by-Step Computation
1. Resolve period and filter returns.
2. Apply configured resampling and optional log transform.
3. Compute sample standard deviation.
4. Annualize and return value or `Insufficient data` error.

## Configuration Options
- `options.frequency`
- `options.annualization_factor`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.VOLATILITY.value`
- `results[period].metrics.VOLATILITY.details.error`

## Worked Example
- Returns pp `[1.00, -0.50, 0.20]`.
- Sample mean `0.2333` and sample std `0.7505` pp.
- With annualization factor `252`, volatility `=0.7505*sqrt(252)=11.914`.
- Output `results[period].metrics.VOLATILITY.value = 11.914`.
- If fewer than 2 observations exist, return `details.error=Insufficient data`.
