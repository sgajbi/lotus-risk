# Drawdown Methodology - Average Drawdown

## Metric
- metric_id: AVERAGE_DRAWDOWN

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/drawdown
- supported_modes: stateless, stateful

## Inputs
- Drawdown path derived from return series.

## Upstream Data Sources
- Derived by drawdown engine.

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
- `U`: underwater subset of drawdown values (`DD_t < 0`).
- `AVG_DD`: average drawdown metric value.

## Methodology and Formulas
1. Convert returns from pp to decimal:
`r_t = r_t_pp / 100`.
2. Build wealth path:
`W_t = ∏_{i=1..t}(1 + r_i)`.
3. Build running peak:
`P_t = max(W_1, W_2, ..., W_t)`.
4. Build drawdown path:
`DD_t = (W_t / P_t) - 1`.
5. Construct underwater set:
`U = {DD_t | DD_t < 0}`.
6. Average drawdown:
`AVG_DD = mean(U)` if `U` is non-empty; otherwise `AVG_DD = 0.0`.

## Step-by-Step Computation
1. Resolve period and select portfolio return observations in that date range.
2. Sort observations by date and convert pp returns to decimal.
3. Compute `W_t`, `P_t`, and `DD_t` for each observation date.
4. Filter drawdown observations where `DD_t < 0`.
5. Compute arithmetic mean over filtered values.
6. If filtered set is empty, set `average_drawdown = 0.0`.
7. Write final value to response summary field.

## Validation and Failure Behavior
- No observations in period: period result is returned with `Insufficient data`.
- One observation only: drawdown path is degenerate; underwater set may be empty, resulting in `average_drawdown = 0.0`.
- Non-numeric returns: rejected by request-contract validation before engine math.
- This metric is independent of episode-list filters (`top_n_episodes`, `minimum_episode_depth_bps`).

## Configuration Options
- No dedicated metric knob.

## Outputs
- `results[period].summary.average_drawdown`

## Worked Example
Input return sequence (pp): Day1 `+5.00`, Day2 `-10.00`, Day3 `+2.00`, Day4 `+4.00`.

| Date | `r_t_pp` | `r_t` (decimal) | `W_t` | `P_t` | `DD_t = W_t/P_t - 1` | Underwater? |
|---|---:|---:|---:|---:|---:|---|
| Day1 | 5.00 | 0.0500 | 1.050000 | 1.050000 | 0.000000 | No |
| Day2 | -10.00 | -0.1000 | 0.945000 | 1.050000 | -0.100000 | Yes |
| Day3 | 2.00 | 0.0200 | 0.963900 | 1.050000 | -0.082000 | Yes |
| Day4 | 4.00 | 0.0400 | 1.002456 | 1.050000 | -0.045280 | Yes |

Underwater subset:
- `U = [-0.100000, -0.082000, -0.045280]`

Average drawdown:
- `AVG_DD = (-0.100000 - 0.082000 - 0.045280) / 3 = -0.075760`

Output mapping:
- `results[period].summary.average_drawdown = -0.075760`
