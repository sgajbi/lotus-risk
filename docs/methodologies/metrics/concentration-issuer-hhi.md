# Concentration Methodology - Issuer HHI

## Metric
- metric_id: ISSUER_HHI
- source_product: ConcentrationRiskReport:v1
- methodology_version: concentration.issuer_hhi.v1

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation
- output_family: `issuer_concentration`

## Inputs
- Current position rows.
- Proposed position rows when the caller supplies or source state resolves a projected state.
- Issuer identifiers supplied on stateless position rows, caller issuer mappings, and/or
  lotus-core enrichment rows.
- `issuer_grouping_level`, which chooses legal issuer grouping or ultimate-parent issuer grouping.
- `enrichment_policy`, which chooses caller-only, core-only, or merged issuer-map precedence.

## Upstream Data Sources
- Stateless mode uses caller-provided `stateless_input.current_positions` and
  `stateless_input.projected_positions`.
- Stateless mode may call lotus-core instrument enrichment when a core client is available and
  `enrichment_policy` is not `use_caller_only`.
- Stateful mode requests a lotus-core baseline snapshot with `positions_baseline`,
  `portfolio_totals`, and `instrument_enrichment`; it uses baseline positions for both current
  and proposed states.
- Simulation mode creates or reuses a lotus-core simulation session, applies requested changes,
  requests a simulation snapshot with `positions_baseline`, `positions_projected`,
  `positions_delta`, `portfolio_totals`, and `instrument_enrichment`, and uses baseline positions
  as current state and projected positions as proposed state.
- There is no lotus-performance dependency for issuer HHI.

## Unit Conventions
- Position inputs are portfolio amount-like values, not return percentages.
- Stateless current rows use `market_value_base` when present; otherwise they fall back to
  `quantity`.
- Stateless projected rows use `projected_market_value_base` when present; otherwise they fall
  back to `proposed_quantity`.
- Stateful and simulation snapshot rows use `market_value_base` when present; otherwise they fall
  back to `quantity`.
- Values are parsed through Decimal from the source value's string representation. Missing,
  non-numeric, zero, and negative values are excluded before issuer aggregation and coverage
  counting.
- Issuer weights are decimal ratios in `[0, 1]`.
- `issuer_concentration.hhi_*` values are emitted on the conventional Herfindahl-Hirschman
  `0..10000` scale and rounded to six decimal places by the service response.

## Variable Dictionary
- `G`: requested issuer grouping level, either legal issuer or ultimate-parent issuer.
- `M`: resolved issuer map keyed by `security_id` after enrichment-policy precedence.
- `C`: current extracted positive numeric position rows.
- `P`: proposed extracted positive numeric position rows.
- `x_i`: one extracted positive current position value in `C`.
- `y_i`: one extracted positive proposed position value in `P`.
- `issuer(i, G, M)`: issuer bucket selected for position `i` under grouping level `G` from map
  `M`.
- `K_C`: issuer buckets with at least one covered current position.
- `K_P`: issuer buckets with at least one covered proposed position.
- `I_{C,k} = sum(abs(x_i)) for covered current positions mapped to issuer bucket k`.
- `I_{P,k} = sum(abs(y_i)) for covered proposed positions mapped to issuer bucket k`.
- `V_C_issuer = sum_k(abs(I_{C,k}))`: covered current issuer denominator.
- `V_P_issuer = sum_k(abs(I_{P,k}))`: covered proposed issuer denominator.
- `w_{C,k} = abs(I_{C,k}) / V_C_issuer` when `V_C_issuer > 0`.
- `w_{P,k} = abs(I_{P,k}) / V_P_issuer` when `V_P_issuer > 0`.
- `ISSUER_HHI_current_raw = sum_k(w_{C,k}^2) * 10000`.
- `ISSUER_HHI_proposed_raw = sum_k(w_{P,k}^2) * 10000`.
- `ISSUER_HHI_delta_raw = ISSUER_HHI_proposed_raw - ISSUER_HHI_current_raw`.
- `covered_position_count_state`: count of extracted positive position rows with a resolved issuer
  bucket in that state.
- `total_position_count_state`: count of extracted positive position rows evaluated for issuer
  coverage in that state.
- `coverage_ratio_state = covered_position_count_state / total_position_count_state` when the
  denominator is non-zero, else `0.0`.
- `round6(z)`: Python `round(z, 6)` used by the service response.

## Methodology and Formulas
For each state:

1. Extract one positive numeric value per usable position row according to the mode-specific
   field precedence.
2. Resolve the issuer map:
   - legal issuer grouping uses `issuer_id`,
   - ultimate-parent grouping uses `ultimate_parent_issuer_id` when present and falls back to
     `issuer_id`,
   - `use_caller_only` uses only caller-supplied issuer identity,
   - `core_only` uses only lotus-core enrichment identity,
   - merged policy starts with lotus-core identity and lets caller identity override by
     `security_id`.
3. Count every extracted positive position row in `total_position_count_state`.
4. For rows with a resolved issuer bucket, add the row value to that issuer bucket and increment
   `covered_position_count_state`.
5. Compute the covered issuer denominator:
   `V_issuer = sum_k(abs(I_k))`.
6. If `V_issuer <= 0`, set issuer HHI to `0.0`.
7. Otherwise compute issuer weights:
   `w_k = abs(I_k) / V_issuer`.
8. Compute issuer HHI:
   `ISSUER_HHI_raw = sum_k(w_k^2) * 10000`.
9. Emit:
   - `issuer_concentration.hhi_current = round6(ISSUER_HHI_current_raw)`
   - `issuer_concentration.hhi_proposed = round6(ISSUER_HHI_proposed_raw)`
   - `issuer_concentration.hhi_delta = round6(ISSUER_HHI_proposed_raw - ISSUER_HHI_current_raw)`

When no proposed issuer buckets are available in stateless or stateful mode, the implemented
service sets `ISSUER_HHI_proposed_raw = ISSUER_HHI_current_raw`; the emitted delta is therefore
`0.0`. Simulation mode is source-owned by lotus-core: missing or invalid `positions_projected` is
an upstream invalid response, while an explicit empty `positions_projected: []` is treated as an
empty proposed book with `ISSUER_HHI_proposed_raw = 0.0`.

## Step-by-Step Computation
1. Resolve request mode.
2. Build current position entries:
   - stateless: caller current positions,
   - stateful: lotus-core baseline positions,
   - simulation: lotus-core baseline positions.
3. Build proposed position entries:
   - stateless: caller projected positions,
   - stateful: same baseline positions as current,
   - simulation: required lotus-core projected positions; an explicit empty list remains empty.
4. Resolve issuer identities from stateless row fields, caller `issuer_mappings`, and/or lotus-core
   enrichment according to grouping and enrichment policy.
5. Parse each state's preferred value field, fall back to the secondary value field, and keep only
   positive numeric values.
6. Aggregate only covered position values by issuer bucket.
7. Compute current and proposed covered-issuer weights.
8. Compute current and proposed issuer HHI on the covered issuer buckets.
9. Reuse current issuer HHI only for modes that intentionally use current state when proposed
   issuer buckets are empty.
10. Compute proposed-minus-current delta.
11. Round emitted HHI values, coverage ratios, and delta fields to six decimal places.
12. Emit issuer coverage counts, coverage ratios, coverage status, supportability, note, and top
    issuer driver metadata alongside issuer HHI.

## Validation and Failure Behavior
- Missing, non-numeric, zero, and negative values are excluded before issuer aggregation and before
  issuer coverage counts.
- Positions without resolved issuer identity are excluded from issuer HHI but included in issuer
  coverage totals.
- Empty current issuer buckets produce `issuer_concentration.hhi_current = 0.0`.
- Empty stateless/stateful proposed issuer buckets fall back to current issuer HHI. Empty
  simulation projected positions produce proposed issuer HHI `0.0`; missing or invalid simulation
  projected sections return `UPSTREAM_INVALID_RESPONSE`.
- A single covered issuer bucket produces issuer HHI `10000.0`.
- Equal weights across `N` covered issuer buckets produce issuer HHI `10000 / N`.
- Partial issuer mapping yields `coverage_status = partial` when at least one current or proposed
  position is covered and at least one evaluated position is uncovered.
- Fully covered current and proposed states yield `coverage_status = complete`.
- No evaluated positions yield `coverage_status = unavailable` and empty calculation
  supportability.
- Evaluated positions with no covered issuer buckets, or an issuer enrichment note, yield degraded
  calculation supportability with reason `calculation_quality_issue`.
- Issuer HHI is computed from the covered subset only; coverage counts, coverage ratios,
  `coverage_status`, `note`, and `metadata.calculation_supportability` carry the data-quality
  posture.
- The position-HHI and single-position outputs are independent; issuer enrichment coverage does
  not change `risk_proxy.hhi_*` or `single_position_concentration.*` outputs.

## Configuration Options
- Direct issuer-HHI options:
  - `issuer_grouping_level`
  - `enrichment_policy`
- Options that can change the source position universe:
  - `include_cash_positions`
  - `include_zero_quantity_positions`
  - `reporting_currency`
- Options that do not change the issuer-HHI formula:
  - `top_n`

## Outputs
- `issuer_concentration.hhi_current`
- `issuer_concentration.hhi_proposed`
- `issuer_concentration.hhi_delta`
- `issuer_concentration.coverage_status`
- `issuer_concentration.covered_position_count_current`
- `issuer_concentration.covered_position_count_proposed`
- `issuer_concentration.total_position_count_current`
- `issuer_concentration.total_position_count_proposed`
- `issuer_concentration.uncovered_position_count_current`
- `issuer_concentration.uncovered_position_count_proposed`
- `issuer_concentration.coverage_ratio_current`
- `issuer_concentration.coverage_ratio_proposed`
- `issuer_concentration.note`
- `issuer_concentration.top_issuer_current`
- `issuer_concentration.top_issuer_proposed`
- `metadata.calculation_supportability`

## Worked Example
Current positions: A=50 and B=30 map to issuer X; C=20 maps to issuer Y.
Proposed positions: A=60 and B=10 map to issuer X; C=30 maps to issuer Y.

| State | Covered Issuer Totals | Covered Denominator | Issuer Weights | Squared Weights | Issuer HHI |
|---|---|---:|---|---|---:|
| Current | `X:80, Y:20` | `100` | `X:0.80, Y:0.20` | `0.6400 + 0.0400` | `6800` |
| Proposed | `X:70, Y:30` | `100` | `X:0.70, Y:0.30` | `0.4900 + 0.0900` | `5800` |

Delta:

`issuer_concentration.hhi_delta = 5800 - 6800 = -1000`.

Output mapping:

- `issuer_concentration.hhi_current = 6800.0`
- `issuer_concentration.hhi_proposed = 5800.0`
- `issuer_concentration.hhi_delta = -1000.0`
- `issuer_concentration.coverage_status = complete`
- `issuer_concentration.covered_position_count_current = 3`
- `issuer_concentration.covered_position_count_proposed = 3`
- `issuer_concentration.total_position_count_current = 3`
- `issuer_concentration.total_position_count_proposed = 3`
- `issuer_concentration.coverage_ratio_current = 1.0`
- `issuer_concentration.coverage_ratio_proposed = 1.0`
