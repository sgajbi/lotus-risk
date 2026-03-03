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

## Variable Dictionary
- `t`: aligned observation index over common portfolio/benchmark dates.
- `Rp_t_pp`: portfolio return at `t` in percentage points.
- `Rb_t_pp`: benchmark return at `t` in percentage points.
- `a_t_pp`: active return in percentage points (`a_t_pp = Rp_t_pp - Rb_t_pp`).
- `a_t`: active return in decimal (`a_t = a_t_pp / 100`).
- `AW_t`: active wealth index up to `t`.
- `AP_t`: active running peak wealth up to `t`.
- `ADD_t`: active drawdown at `t`.
- `REL_MAX_DD`: relative maximum drawdown value.

## Methodology and Formulas
1. Align portfolio and benchmark returns by date (inner join).
2. Compute active return in pp:
`a_t_pp = Rp_t_pp - Rb_t_pp`.
3. Convert active return to decimal:
`a_t = a_t_pp / 100`.
4. Build active wealth path:
`AW_t = ∏_{i=1..t}(1 + a_i)`.
5. Build active running peak:
`AP_t = max(AW_1, AW_2, ..., AW_t)`.
6. Build active drawdown path:
`ADD_t = (AW_t / AP_t) - 1`.
7. Relative maximum drawdown:
`REL_MAX_DD = min_t(ADD_t)`.

## Step-by-Step Computation
1. Resolve period window and collect portfolio and benchmark series for that period.
2. Apply inner-date alignment between the two series.
3. If aligned set is empty, relative drawdown summary is omitted (`relative_to_benchmark = null`).
4. Compute active return series (`a_t_pp`, then `a_t` decimal).
5. Compute active wealth (`AW_t`), active running peak (`AP_t`), and active drawdown (`ADD_t`).
6. Compute `REL_MAX_DD = min(ADD_t)`.
7. Identify trough date (`argmin(ADD_t)`) and prior active-wealth peak date.
8. Map relative drawdown values and dates into `relative_to_benchmark` summary fields.

## Validation and Failure Behavior
- Benchmark returns are required for relative drawdown output.
- If benchmark exists but no overlapping dates with portfolio series, relative summary is `null` (alignment-empty behavior).
- Non-numeric return values are rejected by request-contract validation before engine math.
- Relative drawdown value is non-positive by construction (`<= 0`).

## Configuration Options
- Benchmark data must be present and date-alignable with portfolio returns.
- No dedicated metric-specific tuning parameter beyond period selection.

## Outputs
- `results[period].relative_to_benchmark.max_drawdown`
- `results[period].relative_to_benchmark.max_drawdown_peak_date`
- `results[period].relative_to_benchmark.max_drawdown_trough_date`

## Worked Example
Input series (all dates overlap):
- Portfolio pp: Day1 `1.0`, Day2 `-2.0`, Day3 `0.5`
- Benchmark pp: Day1 `0.5`, Day2 `-1.0`, Day3 `0.2`

| Date | `Rp_t_pp` | `Rb_t_pp` | `a_t_pp = Rp_t_pp - Rb_t_pp` | `a_t` (decimal) | `AW_t` | `AP_t` | `ADD_t = AW_t/AP_t - 1` |
|---|---:|---:|---:|---:|---:|---:|---:|
| Day1 | 1.0 | 0.5 | 0.5 | 0.0050 | 1.005000 | 1.005000 | 0.000000 |
| Day2 | -2.0 | -1.0 | -1.0 | -0.0100 | 0.994950 | 1.005000 | -0.010000 |
| Day3 | 0.5 | 0.2 | 0.3 | 0.0030 | 0.997935 | 1.005000 | -0.007030 |

Derived outputs:
- `REL_MAX_DD = min(ADD_t) = -0.010000` (=-1.00%).
- Relative peak date = Day1.
- Relative trough date = Day2.

Output mapping:
- `results[period].relative_to_benchmark.max_drawdown = -0.010000`
- `results[period].relative_to_benchmark.max_drawdown_peak_date = Day1`
- `results[period].relative_to_benchmark.max_drawdown_trough_date = Day2`
