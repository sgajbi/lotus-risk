# Drawdown Methodology - Relative Maximum Drawdown

## Metric
- metric_id: RELATIVE_MAX_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Portfolio and benchmark return series.

## Upstream Data Sources
- Stateless caller or stateful lotus-performance.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Active return path: `a_t = Rp_t - Rb_t` (pp).
2. Active wealth path: `AW_t = Π(1 + a_t/100)`.
3. Active running peak: `AP_t = cummax(AW_t)`.
4. Active drawdown path: `ADD_t = AW_t / AP_t - 1`.
5. Relative maximum drawdown: `REL_MAX_DD = min(ADD_t)`.

## Step-by-Step Computation
1. Align portfolio and benchmark returns on common dates.
2. Compute active return, wealth, and drawdown paths.
3. Identify minimum active drawdown value.
4. Map corresponding peak and trough dates into relative summary fields.

## Configuration Options
- Benchmark data must be present.

## Outputs
- `results[period].relative_to_benchmark.max_drawdown` and date fields.

## Worked Example
- Portfolio pp `[1.0,-2.0,0.5]`, benchmark pp `[0.5,-1.0,0.2]`.
- Active pp `[0.5,-1.0,0.3]` -> decimal `[0.005,-0.010,0.003]`.
- Active wealth `[1.005000,0.994950,0.997935]` with peak `1.005000`.
- Active drawdown `[0.0000,-0.0100,-0.0070]`.
- Relative max drawdown is `-0.0100` (=-1.00%).