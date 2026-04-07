# Concentration API Integration Guide

## Endpoint

- `POST /analytics/risk/concentration`

## Purpose

Compute portfolio concentration analytics from current and proposed holdings using one canonical contract across:

- `stateless`
- `stateful`
- `simulation`

The API returns three decision-oriented blocks:

1. `risk_proxy`
   - portfolio-level HHI
   - current / proposed / delta
2. `single_position_concentration`
   - top position weight
   - top-`n` cumulative weight
   - identity of the top position in each state
3. `issuer_concentration`
   - issuer-level HHI
   - top issuer weight
   - identity of the top issuer in each state
   - issuer coverage diagnostics

## Supported Modes

### `stateless`

Caller provides:

- `stateless_input.current_positions`
- `stateless_input.projected_positions`

`lotus-risk` computes concentration directly from caller-supplied values. Position values use:

1. `market_value_base` when present
2. `quantity` as fallback

### `stateful`

Caller provides:

- `stateful_input.portfolio_id`
- `stateful_input.as_of_date`

`lotus-risk` calls lotus-core `core-snapshot` in `BASELINE` mode and computes concentration from the baseline portfolio state.

### `simulation`

Caller provides:

- `simulation_input.portfolio_id`
- `simulation_input.as_of_date`
- `simulation_input.simulation_changes`

`lotus-risk` orchestrates lotus-core simulation session APIs, then calls lotus-core `core-snapshot` in `SIMULATION` mode to evaluate baseline vs projected concentration.

## Canonical Request Envelope

```json
{
  "input_mode": "stateless | stateful | simulation",
  "stateless_input": {},
  "stateful_input": {},
  "simulation_input": {},
  "issuer_grouping_level": "ultimate_parent | legal_issuer",
  "enrichment_policy": "merge_caller_then_core | use_caller_only | core_only"
}
```

Legacy camelCase aliases are not supported.

## Issuer Grouping and Enrichment

### `issuer_grouping_level`

- `ultimate_parent`
  - default
  - groups positions by ultimate parent issuer when available, else legal issuer fallback
- `legal_issuer`
  - groups positions by legal issuer only

### `enrichment_policy`

- `merge_caller_then_core`
  - default
  - caller mappings win
  - lotus-core fills gaps
- `use_caller_only`
  - only caller-supplied issuer mappings are used
- `core_only`
  - only lotus-core enrichment is used

### Caller-supplied issuer mapping inputs

#### `stateless`

Caller can provide issuer keys directly on each position row:

- `issuer_id`
- `ultimate_parent_issuer_id`

Optional display fields may also be provided on positions:

- `security_name`

#### `stateful` / `simulation`

Caller can provide `issuer_mappings[]` keyed by `security_id`, while lotus-core `instrument_enrichment` remains the primary source of canonical issuer enrichment.

## Calculation Behavior

### Portfolio HHI

For any state:

- `v_i = abs(position_value_i)`
- `V = sum_i v_i`
- `w_i = v_i / V`
- `HHI = sum_i (w_i^2) * 10000`

If no valid positive values are available, HHI is `0`.

### Single-position concentration

For each state:

- `top_position_weight = max_i(w_i)`
- `top_n_cumulative_weight = sum of largest n position weights`

The response also identifies the top position:

- `single_position_concentration.top_position_current`
- `single_position_concentration.top_position_proposed`

These fields contain:

- `security_id`
- `security_name`
- `weight`

### Issuer concentration

1. Resolve issuer key per position using `issuer_grouping_level`.
2. Aggregate position values by issuer.
3. Compute issuer weights from issuer-level totals.
4. Compute issuer HHI and top issuer weight.

The response also identifies the top issuer:

- `issuer_concentration.top_issuer_current`
- `issuer_concentration.top_issuer_proposed`

These fields contain:

- `issuer_id`
- `issuer_name`
- `weight`

## Coverage Semantics

`issuer_concentration` is always returned, even when enrichment is incomplete.

Coverage fields:

- `coverage_status`
  - `complete`
  - `partial`
  - `unavailable`
- `covered_position_count_current`
- `covered_position_count_proposed`
- `total_position_count_current`
- `total_position_count_proposed`
- `note`

Interpretation:

1. `complete`
   - every counted position was mapped to an issuer key
2. `partial`
   - at least one position was mapped, but some were not
3. `unavailable`
   - no issuer mapping coverage was available for the counted positions

No silent fallback is allowed. If issuer enrichment is incomplete, the response makes that explicit through coverage fields.

## Cash Handling

`include_cash_positions` materially changes the concentration denominator.

Business interpretation:

- `true`
  - concentration is measured against the full portfolio including cash
  - useful when cash is part of the investable balance the banker is monitoring
- `false`
  - concentration is measured only across invested positions
  - useful when the banker wants a pure invested-book concentration view

## Simulation Session Semantics

1. If `session_id` is absent or `start_new_session=true`, lotus-risk creates a new lotus-core simulation session.
2. `simulation_changes[]` are forwarded to lotus-core for the resolved session.
3. Changes are additive within the session unless a new session is started.
4. `expected_version` can be supplied for optimistic concurrency.
5. The response returns simulation metadata when available:
   - `metadata.simulation_session_id`
   - `metadata.simulation_session_version`
   - `metadata.session_expires_at`

## Upstream Dependencies

### lotus-core

Required APIs:

1. `POST /integration/portfolios/{portfolio_id}/core-snapshot`
   - baseline or simulation snapshot
   - positions
   - portfolio totals
   - instrument enrichment
2. `POST /simulation-sessions`
3. `POST /simulation-sessions/{session_id}/changes`
4. bulk instrument enrichment for stateless enrichment fallback

There is no lotus-performance dependency for concentration.

## Response Blocks

### `risk_proxy`

- `hhi_current`
- `hhi_proposed`
- `hhi_delta`

### `single_position_concentration`

- `top_position_weight_current`
- `top_position_weight_proposed`
- `top_position_weight_delta`
- `top_n_cumulative_weight_current`
- `top_n_cumulative_weight_proposed`
- `top_n_cumulative_weight_delta`
- `top_n`
- `top_position_current`
- `top_position_proposed`

### `issuer_concentration`

- `hhi_current`
- `hhi_proposed`
- `hhi_delta`
- `top_issuer_weight_current`
- `top_issuer_weight_proposed`
- `top_issuer_weight_delta`
- `coverage_status`
- coverage counters
- `note`
- `top_issuer_current`
- `top_issuer_proposed`

### `valuation_context`

When provided by lotus-core:

- `portfolio_currency`
- `reporting_currency`
- `position_basis`
- `weight_basis`

### `metadata`

Depending on mode:

- `portfolio_id`
- `as_of_date`
- simulation session metadata
