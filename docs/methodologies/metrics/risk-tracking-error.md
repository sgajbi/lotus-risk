# Risk Metric Methodology - Tracking Error

## Metric
- metric_id: TRACKING_ERROR

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio and benchmark returns.
- Annualization basis.

## Upstream Data Sources
- Stateless caller.
- Stateful lotus-performance.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Active return vector: `a_t = Rp_t - Rb_t`.
2. Sample active volatility: `sigma_a = std(a_t, ddof=1)`.
3. Annualized tracking error: `TE = sigma_a * sqrt(annualization_factor)`.

## Step-by-Step Computation
1. Align portfolio and benchmark returns by date and period.
2. Compute active return at each aligned point.
3. Compute sample standard deviation of active return.
4. Apply annualization factor and emit metric value.

## Configuration Options
- `options.frequency`
- `options.annualization_factor`

## Outputs
- `results[period].metrics.TRACKING_ERROR.value`

## Worked Example
- Aligned portfolio and benchmark returns produce active pp `[0.1,-0.2,0.1]`.
- Active mean is `0`; sample std is `0.1732` pp.
- Annualization factor `252`.
- TE = `0.1732*sqrt(252)=2.749` pp.
- Output field stores annualized TE value.