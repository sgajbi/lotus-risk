# Drawdown Methodology - Ulcer Index

## Metric
- metric_id: ULCER_INDEX

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Drawdown path over period.

## Upstream Data Sources
- Derived in drawdown engine.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Variable Dictionary
- `t`: observation index in chronological order.
- `r_t_pp`: period return at index `t` in percentage points.
- `r_t`: period return at index `t` in decimal (`r_t = r_t_pp / 100`).
- `W_t`: cumulative wealth index up to `t`.
- `P_t`: running peak wealth up to `t`.
- `DD_t`: drawdown at `t`.
- `SQ_t`: squared drawdown (`DD_t^2`).
- `UI`: ulcer index.

## Methodology and Formulas
1. Convert returns from pp to decimal:
`r_t = r_t_pp / 100`.
2. Build wealth path:
`W_t = ∏_{i=1..t}(1 + r_i)`.
3. Build running peak:
`P_t = max(W_1, W_2, ..., W_t)`.
4. Build drawdown path:
`DD_t = (W_t / P_t) - 1`.
5. Square drawdowns:
`SQ_t = DD_t^2`.
6. Ulcer index:
`UI = sqrt(mean_t(SQ_t))`.

## Step-by-Step Computation
1. Resolve period and filter return observations to analysis window.
2. Sort returns by date and convert pp values to decimal.
3. Compute `W_t`, `P_t`, and `DD_t` for each timestamp.
4. Square each `DD_t` to produce `SQ_t`.
5. Compute arithmetic mean of all `SQ_t` values in the period.
6. Take square root of this mean to obtain `UI`.
7. Return `UI` as non-negative decimal in summary payload.

## Validation and Failure Behavior
- No observations in period: period result carries `Insufficient data`.
- Single observation: `DD_t` is `0`, so `UI = 0`.
- Non-numeric returns: rejected by request-contract validation before engine computation.
- Ulcer index is always `>= 0` by construction (square then square-root).

## Configuration Options
- No dedicated metric knob.

## Outputs
- `results[period].summary.ulcer_index`

## Worked Example
Input return sequence (pp): Day1 `+5.00`, Day2 `-10.00`, Day3 `+2.00`, Day4 `+4.00`.

| Date | `r_t_pp` | `r_t` (decimal) | `W_t` | `P_t` | `DD_t` | `SQ_t = DD_t^2` |
|---|---:|---:|---:|---:|---:|---:|
| Day1 | 5.00 | 0.0500 | 1.050000 | 1.050000 | 0.000000 | 0.000000 |
| Day2 | -10.00 | -0.1000 | 0.945000 | 1.050000 | -0.100000 | 0.010000 |
| Day3 | 2.00 | 0.0200 | 0.963900 | 1.050000 | -0.082000 | 0.006724 |
| Day4 | 4.00 | 0.0400 | 1.002456 | 1.050000 | -0.045280 | 0.002050 |

Intermediate aggregation:
- `mean(SQ_t) = (0.000000 + 0.010000 + 0.006724 + 0.002050) / 4 = 0.004694`

Final metric:
- `UI = sqrt(0.004694) = 0.068513`

Output mapping:
- `results[period].summary.ulcer_index = 0.068513`
