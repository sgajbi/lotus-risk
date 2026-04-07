# Concentration Methodology - Issuer HHI

## Metric
- metric_id: ISSUER_HHI

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Position values plus issuer mapping (issuer or ultimate parent).
- Issuer enrichment policy and grouping level.

## Upstream Data Sources
- Caller mapping and/or lotus-core enrichment.
- Stateful/simulation snapshots from lotus-core.

## Unit Conventions
- Position inputs are non-negative portfolio amounts:
  - `market_value_base` when available
  - `quantity` as fallback when market value is unavailable
- Issuer weights are decimals in `[0, 1]`.
- Issuer HHI is reported on the conventional `0..10000` scale.

## Variable Dictionary
- `security_id`: instrument identifier in position rows.
- `issuer_key`: issuer bucket key chosen by grouping level.
- `issuer_value_k`: aggregate value for issuer bucket `k`.
- `W_issuer = sum_k |issuer_value_k|`: absolute issuer total.
- `w_k = |issuer_value_k|/W_issuer`: issuer weight.
- `ISSUER_HHI = sum_k(w_k^2)*10000`.
- Coverage counters: covered vs total position count for each state.
- `coverage_ratio = covered_position_count / total_position_count` when total count is non-zero, else `0`.

## Methodology and Formulas
1. Resolve issuer key per position.
2. Aggregate values per issuer.
3. Compute issuer weights.
4. Compute `ISSUER_HHI = sum_k (w_k^2) * 10000`.
5. Compute issuer HHI delta.

## Step-by-Step Computation
1. Resolve issuer map and coverage counts.
2. Build current/proposed issuer totals.
3. Normalize to weights.
4. Compute HHI current/proposed/delta.
5. Emit coverage status and counts.
6. Emit coverage ratios for current and proposed states.

## Validation and Failure Behavior
- Partial mapping yields `coverage_status=PARTIAL`.
- No mapped issuer values produce HHI `0` with non-complete coverage.
- The metric is computed on the covered subset only; coverage counters explain data quality.
- If total position count is `0`, coverage ratio is emitted as `0`.

## Configuration Options
- `issuer_grouping_level`
- `enrichment_policy`
- Stateful and simulation input options may also change the covered universe:
  - `include_cash_positions`
  - `include_zero_quantity_positions`

## Outputs
- `issuer_concentration.hhi_current`
- `issuer_concentration.hhi_proposed`
- `issuer_concentration.hhi_delta`
- `issuer_concentration.coverage_status`
- `issuer_concentration.covered_position_count_current`
- `issuer_concentration.covered_position_count_proposed`
- `issuer_concentration.total_position_count_current`
- `issuer_concentration.total_position_count_proposed`
- `issuer_concentration.coverage_ratio_current`
- `issuer_concentration.coverage_ratio_proposed`
- `issuer_concentration.note`
- `issuer_concentration.top_issuer_current`
- `issuer_concentration.top_issuer_proposed`

## Worked Example
Issuer totals current: X=80, Y=20; proposed: X=70, Y=30.
| State | Issuer Totals | Issuer Weights | Squared Weights | Issuer HHI |
|---|---|---|---:|
| Current | `X:80, Y:20` | `X:0.80, Y:0.20` | `X:0.6400, Y:0.0400` | `6800` |
| Proposed | `X:70, Y:30` | `X:0.70, Y:0.30` | `X:0.4900, Y:0.0900` | `5800` |
Delta: `5800 - 6800 = -1000`.
Output mapping:
- `issuer_concentration.hhi_current=6800`
- `issuer_concentration.hhi_proposed=5800`
- `issuer_concentration.hhi_delta=-1000`
- `issuer_concentration.coverage_ratio_current=1.0`
- `issuer_concentration.coverage_ratio_proposed=1.0`
- if both issuer buckets are fully mapped, `issuer_concentration.coverage_status=complete`
