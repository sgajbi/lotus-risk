# Concentration Methodology - Top Issuer Weight

## Metric
- metric_id: TOP_ISSUER_WEIGHT
- source_product: ConcentrationRiskReport:v1
- methodology_version: concentration.top_issuer_weight.v1

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
- There is no lotus-performance dependency for top issuer weight.

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
- Top issuer weights are decimal ratios in `[0, 1]` and are rounded to six decimal places by the
  service response.

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
- `TOP_ISSUER_current_raw = max_k(w_{C,k})` when current issuer buckets exist, else `0.0`.
- `TOP_ISSUER_proposed_raw = max_k(w_{P,k})` when proposed issuer buckets exist, else the current
  top issuer weight.
- `TOP_ISSUER_delta_raw = TOP_ISSUER_proposed_raw - TOP_ISSUER_current_raw`.
- `top_issuer_current`: the current issuer bucket with the largest absolute aggregate issuer
  value; ties choose the lexicographically largest `issuer_id`.
- `top_issuer_proposed`: the proposed issuer bucket with the largest absolute aggregate issuer
  value; when proposed issuer buckets are unavailable it falls back to `top_issuer_current`.
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
3. Aggregate covered rows by issuer bucket.
4. Compute the covered issuer denominator:
   `V_issuer = sum_k(abs(I_k))`.
5. If `V_issuer <= 0`, set top issuer weight to `0.0` and emit an empty top issuer driver.
6. Otherwise compute issuer weights:
   `w_k = abs(I_k) / V_issuer`.
7. Select the largest issuer weight:
   `TOP_ISSUER_raw = max_k(w_k)`.
8. Select the top issuer driver from issuer aggregate values using:
   `max(abs(I_k), issuer_id)`; the secondary `issuer_id` sort makes ties deterministic.
9. Emit:
   - `issuer_concentration.top_issuer_weight_current = round6(TOP_ISSUER_current_raw)`
   - `issuer_concentration.top_issuer_weight_proposed = round6(TOP_ISSUER_proposed_raw)`
   - `issuer_concentration.top_issuer_weight_delta = round6(TOP_ISSUER_proposed_raw - TOP_ISSUER_current_raw)`
   - `issuer_concentration.top_issuer_current.weight = round6(TOP_ISSUER_current_raw)`
   - `issuer_concentration.top_issuer_proposed.weight = round6(TOP_ISSUER_proposed_raw)`

When no proposed issuer buckets are available, the implemented service sets
`TOP_ISSUER_proposed_raw = TOP_ISSUER_current_raw` and reuses the current top issuer driver; the
emitted delta is therefore `0.0`.

## Step-by-Step Computation
1. Resolve request mode.
2. Build current position entries:
   - stateless: caller current positions,
   - stateful: lotus-core baseline positions,
   - simulation: lotus-core baseline positions.
3. Build proposed position entries:
   - stateless: caller projected positions,
   - stateful: same baseline positions as current,
   - simulation: lotus-core projected positions when available.
4. Resolve issuer identities from stateless row fields, caller `issuer_mappings`, and/or lotus-core
   enrichment according to grouping and enrichment policy.
5. Parse each state's preferred value field, fall back to the secondary value field, and keep only
   positive numeric values.
6. Aggregate only covered position values by issuer bucket.
7. Normalize current and proposed issuer aggregates into covered-issuer weights.
8. Select current and proposed top issuer weight from the maximum covered-issuer weight.
9. Select current and proposed top issuer driver metadata from the same issuer aggregate universe,
   using issuer id as the deterministic tie-breaker.
10. If proposed issuer buckets are empty, reuse current top issuer weight and current top issuer
    driver for proposed output.
11. Compute proposed-minus-current delta.
12. Round emitted top issuer weights and delta fields to six decimal places.
13. Emit issuer coverage counts, coverage ratios, coverage status, supportability, and note
    alongside top issuer weight.

## Validation and Failure Behavior
- Missing, non-numeric, zero, and negative values are excluded before issuer aggregation and before
  issuer coverage counts.
- Positions without resolved issuer identity are excluded from top issuer weight but included in
  issuer coverage totals.
- Empty current issuer buckets produce `issuer_concentration.top_issuer_weight_current = 0.0` and
  `issuer_concentration.top_issuer_current.issuer_id = null`.
- Empty proposed issuer buckets do not create an error; proposed top issuer weight and proposed
  top issuer driver fall back to current state.
- A single covered issuer bucket produces top issuer weight `1.0`.
- Equal weights across `N` covered issuer buckets produce top issuer weight `1 / N`; top issuer
  driver identity uses the lexicographically largest `issuer_id` as the tie-breaker.
- Partial issuer mapping yields `coverage_status = partial` when at least one current or proposed
  position is covered and at least one evaluated position is uncovered.
- Fully covered current and proposed states yield `coverage_status = complete`.
- No evaluated positions yield `coverage_status = unavailable` and empty calculation
  supportability.
- Evaluated positions with no covered issuer buckets, or an issuer enrichment note, yield degraded
  calculation supportability with reason `calculation_quality_issue`.
- Top issuer weight is computed from the covered subset only; coverage counts, coverage ratios,
  `coverage_status`, `note`, and `metadata.calculation_supportability` carry the data-quality
  posture.
- The position-HHI and single-position outputs are independent; issuer enrichment coverage does
  not change `risk_proxy.hhi_*` or `single_position_concentration.*` outputs.

## Configuration Options
- Direct top-issuer options:
  - `issuer_grouping_level`
  - `enrichment_policy`
- Options that can change the source position universe:
  - `include_cash_positions`
  - `include_zero_quantity_positions`
  - `reporting_currency`
- Options that do not change the top-issuer formula:
  - `top_n`

## Outputs
- `issuer_concentration.top_issuer_weight_current`
- `issuer_concentration.top_issuer_weight_proposed`
- `issuer_concentration.top_issuer_weight_delta`
- `issuer_concentration.top_issuer_current`
- `issuer_concentration.top_issuer_proposed`
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
- `metadata.calculation_supportability`

## Worked Example
Current positions: A=50 and B=30 map to issuer X; C=20 maps to issuer Y.
Proposed positions: A=60 and B=10 map to issuer X; C=30 maps to issuer Y.

| State | Covered Issuer Totals | Covered Denominator | Issuer Weights | Top Issuer | Top Issuer Weight |
|---|---|---:|---|---|---:|
| Current | `X:80, Y:20` | `100` | `X:0.80, Y:0.20` | `X` | `0.80` |
| Proposed | `X:70, Y:30` | `100` | `X:0.70, Y:0.30` | `X` | `0.70` |

Delta:

`issuer_concentration.top_issuer_weight_delta = 0.70 - 0.80 = -0.10`.

Output mapping:

- `issuer_concentration.top_issuer_weight_current = 0.80`
- `issuer_concentration.top_issuer_weight_proposed = 0.70`
- `issuer_concentration.top_issuer_weight_delta = -0.10`
- `issuer_concentration.top_issuer_current.issuer_id = "ISSUER_X"`
- `issuer_concentration.top_issuer_current.weight = 0.80`
- `issuer_concentration.top_issuer_proposed.issuer_id = "ISSUER_X"`
- `issuer_concentration.top_issuer_proposed.weight = 0.70`
