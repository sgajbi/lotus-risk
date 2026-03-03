# Risk Metric Methodology - Sortino Ratio

## Metric
- metric_id: SORTINO

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio return series in pp.
- Minimum acceptable return annual rate.

## Upstream Data Sources
- Stateless caller returns.
- Stateful lotus-performance returns.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Convert MAR annual rate to periodic threshold: `mar_p = (1+mar_annual)^(1/annual_factor)-1`.
2. Downside excess vector: `d_t = r_t/100 - mar_p` for `d_t < 0`.
3. Downside deviation: `sigma_down = sqrt(mean(d_t^2))`.
4. Sortino ratio: `SORTINO = ((mean(r_t)/100 - mar_p) / sigma_down) * sqrt(annual_factor)`.

## Step-by-Step Computation
1. Resolve period returns and periodic MAR threshold.
2. Build downside-only vector below MAR.
3. If downside vector is empty, emit `No downside observations` error.
4. Compute downside deviation and annualized Sortino ratio.

## Configuration Options
- `options.mar_annual_rate`
- `options.annualization_factor`

## Outputs
- `results[period].metrics.SORTINO.value`
- `...details.error`

## Worked Example
- Decimal returns `[0.0100,-0.0200,0.0050]`, MAR `0`.
- Downside vector is `[-0.0200]` (only values below MAR).
- Downside deviation `sqrt(mean(0.0200^2))=0.0200`.
- Mean return `-0.001667`; Sortino `=(-0.001667/0.0200)*sqrt(252)=-1.323`.
- If downside set is empty, engine returns `No downside observations`.