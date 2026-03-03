# Drawdown Methodology - Time Under Water

## Metric
- metric_id: TIME_UNDER_WATER_DAYS

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
- `I_t`: indicator variable, `1` if `DD_t < 0`, otherwise `0`.
- `TUW`: time-under-water count over the period.

## Methodology and Formulas
1. Convert returns from pp to decimal:
`r_t = r_t_pp / 100`.
2. Build wealth path:
`W_t = ∏_{i=1..t}(1 + r_i)`.
3. Build running peak:
`P_t = max(W_1, W_2, ..., W_t)`.
4. Build drawdown path:
`DD_t = (W_t / P_t) - 1`.
5. Build indicator series:
`I_t = 1` when `DD_t < 0`; else `I_t = 0`.
6. Time-under-water metric:
`TUW = Σ_t I_t`.

## Step-by-Step Computation
1. Resolve period and filter portfolio returns to that date range.
2. Sort observations by date and convert pp returns to decimal.
3. Compute `W_t`, `P_t`, and `DD_t` for each observation date.
4. Mark each row with indicator `I_t = 1` if `DD_t < 0`, else `0`.
5. Sum indicators across all rows to get `TUW`.
6. Return integer `TUW` in summary payload.
7. Interpret as persistence measure (duration-like count), not a depth measure.

## Validation and Failure Behavior
- No observations in period: period result carries `Insufficient data`.
- Single observation: `DD_t = 0`, therefore `TUW = 0`.
- Non-numeric returns: rejected by request-contract validation before engine computation.
- `duration_unit` option affects episode-day fields, not `time_under_water_days` counting logic.

## Configuration Options
- No dedicated metric knob.

## Outputs
- `results[period].summary.time_under_water_days`

## Worked Example
Input return sequence (pp): Day1 `+5.00`, Day2 `-10.00`, Day3 `+2.00`, Day4 `+4.00`.

| Date | `r_t_pp` | `r_t` (decimal) | `W_t` | `P_t` | `DD_t` | `I_t = 1(DD_t<0)` |
|---|---:|---:|---:|---:|---:|---:|
| Day1 | 5.00 | 0.0500 | 1.050000 | 1.050000 | 0.000000 | 0 |
| Day2 | -10.00 | -0.1000 | 0.945000 | 1.050000 | -0.100000 | 1 |
| Day3 | 2.00 | 0.0200 | 0.963900 | 1.050000 | -0.082000 | 1 |
| Day4 | 4.00 | 0.0400 | 1.002456 | 1.050000 | -0.045280 | 1 |

Aggregation:
- `TUW = 0 + 1 + 1 + 1 = 3`

Output mapping:
- `results[period].summary.time_under_water_days = 3`
