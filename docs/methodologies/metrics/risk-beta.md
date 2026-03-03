# Risk Metric Methodology - Beta

## Metric
- metric_id: BETA

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio and benchmark return series in pp.

## Upstream Data Sources
- Stateless caller provides both.
- Stateful lotus-performance provides both.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Align portfolio and benchmark return series on common dates (inner join).
2. Compute sample covariance `cov(Rp,Rb,ddof=1)`.
3. Compute sample benchmark variance `var(Rb,ddof=1)`.
4. Beta definition: `BETA = cov(Rp,Rb) / var(Rb)`.

## Step-by-Step Computation
1. Build aligned period return matrix with portfolio and benchmark columns.
2. Validate at least two aligned observations.
3. Compute covariance and benchmark variance.
4. If benchmark variance is zero, return deterministic metric error.
5. Otherwise return beta value.

## Configuration Options
- `options.frequency`
- `options.use_log_returns`

## Outputs
- `results[period].metrics.BETA.value`
- `...details.error`

## Worked Example
- Portfolio pp `[1.0,-1.0,2.0]`, benchmark pp `[0.5,-0.5,1.0]`.
- Covariance and variance computed on aligned dates with ddof=1.
- Since portfolio is exactly 2x benchmark each date, `cov(Rp,Rb)=2*var(Rb)`.
- Beta `= cov/var = 2.0`.
- If benchmark variance is zero, response emits `details.error`.