# Risk Metric Methodology - Information Ratio

## Metric
- metric_id: INFORMATION_RATIO

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
2. Active mean: `mu_a = mean(a_t)`.
3. Active volatility: `sigma_a = std(a_t, ddof=1)`.
4. Information ratio: `IR = (mu_a / sigma_a) * sqrt(annualization_factor)`.

## Step-by-Step Computation
1. Align portfolio and benchmark series.
2. Compute active return vector and its sample moments.
3. Validate non-zero `sigma_a`; otherwise emit deterministic error.
4. Annualize and return information ratio.

## Configuration Options
- `options.frequency`
- `options.annualization_factor`

## Outputs
- `results[period].metrics.INFORMATION_RATIO.value`
- `...details.error`

## Worked Example
- Active pp returns `[0.2,0.1,-0.1,0.0]`.
- Active mean `0.05`; sample std `0.1291`.
- Annualization `252`.
- IR `=(0.05/0.1291)*sqrt(252)=6.146`.
- If active std is zero, response emits `Tracking error is zero`.