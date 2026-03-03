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
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when required: `r_decimal = r_pp / 100`.
- Output units are metric-specific (ratio, annualized pp, decimal drawdown, or HHI scale).

## Variable Dictionary
- `security_id`: instrument identifier in position rows.
- `issuer_key`: issuer bucket key chosen by grouping level.
- `issuer_value_k`: aggregate value for issuer bucket `k`.
- `W_issuer = sum_k |issuer_value_k|`: absolute issuer total.
- `w_k = |issuer_value_k|/W_issuer`: issuer weight.
- `ISSUER_HHI = sum_k(w_k^2)*10000`.
- Coverage counters: covered vs total position count for each state.

## Methodology and Formulas
1. Resolve issuer key per position.
2. Aggregate values per issuer.
3. Compute issuer weights.
4. Compute issuer HHI and delta.

## Step-by-Step Computation
1. Resolve issuer map and coverage counts.
2. Build current/proposed issuer totals.
3. Normalize to weights.
4. Compute HHI current/proposed/delta.
5. Emit coverage status and counts.

## Validation and Failure Behavior
- Partial mapping yields `coverage_status=PARTIAL`.
- No mapped issuer values can produce HHI `0` with non-complete coverage.

## Configuration Options
- `issuer_options.grouping_level`
- `issuer_options.enrichment_policy`
- `issuer_options.allow_partial_coverage`

## Outputs
- `issuer_concentration.hhi_current`
- `issuer_concentration.hhi_proposed`
- `issuer_concentration.hhi_delta`
- `issuer_concentration.coverage_status`

## Worked Example
Issuer totals current: X=80, Y=20; proposed: X=70, Y=30.
| State | Issuer Totals | Issuer Weights | Issuer HHI |
|---|---|---|---:|
| Current | `X:80, Y:20` | `X:0.80, Y:0.20` | `6800` |
| Proposed | `X:70, Y:30` | `X:0.70, Y:0.30` | `5800` |
Delta: `5800 - 6800 = -1000`.
Output mapping: `issuer_concentration.hhi_current=6800`, `...hhi_proposed=5800`, `...hhi_delta=-1000`.