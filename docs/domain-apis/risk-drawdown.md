# Risk Drawdown Endpoint Assessment

## Endpoint

- `POST /analytics/risk/drawdown`

## Purpose

- Compute realized drawdown analytics for historical/current portfolio behavior, including:
  - maximum drawdown
  - drawdown episodes
  - time-under-water
  - ulcer index
  - drawdown-at-risk and conditional drawdown-at-risk

## Execution Mode Support

### Stateless

- Status: implemented
- Behavior:
  - caller provides full return series and period config
  - lotus-risk computes drawdown analytics directly

### Stateful

- Status: implemented
- Behavior:
  - caller provides identifiers and period config
  - lotus-risk sources canonical return series from lotus-performance (`/integration/returns/series`, `input_mode=stateful`, `stateful_input is an empty envelope; consumer identity is stamped by lotus-performance server-side`)
  - lotus-risk computes drawdown analytics on sourced series

### Simulation

- Status: intentionally unsupported in the current production contract
- Reason:
  - realized drawdown depends on a historical return path
  - a projected holdings snapshot is not enough to produce a valid realized drawdown series

## Request Shape (Canonical)

- `input_mode: "stateless" | "stateful"`
- `analysis_options`
  - `include_underwater_series`
  - `include_episode_list`
  - `top_n_episodes`
  - `cdar_alpha`
  - `minimum_episode_depth_bps`
  - `duration_unit`
- `stateless_input` or `stateful_input` (mode-dependent)

## Output Shape

- `source_service`
- `input_mode`
- `scope`
- `results[period_name]`
  - `start_date`
  - `end_date`
  - `summary` (max drawdown, timing, TUW, ulcer, DaR/CDaR)
  - `episodes[]` (top-N worst by depth)
  - `relative_to_benchmark` (optional; active drawdown depth plus timing/recovery fields)
  - `underwater_series` (optional)
  - `error` (period-level deterministic error when data is insufficient)
- `metadata`
  - `contract_version`
  - `methodology_version`
  - applied analysis options
  - applied benchmark policy

## Upstream / Downstream Contracts

- Upstream:
  - lotus-performance returns-series API for stateful mode
  - lotus-core indirectly through lotus-performance stateful sourcing and reference contracts
- Downstream:
  - lotus-report
  - lotus-gateway
  - future PB/WM advisory channels

## Alignment Assessment

- Bounded context ownership: aligned (`lotus-risk` remains analytics owner).
- Vocabulary and API governance: aligned with RFC-0067 (snake_case canonical names, no alias terms).
- Mode envelope consistency: aligned with existing risk/concentration patterns.

## Response Auditability

The response metadata now echoes the applied drawdown configuration so consumers can interpret results without reconstructing the request:

- `include_underwater_series`
- `include_episode_list`
- `top_n_episodes`
- `cdar_alpha`
- `minimum_episode_depth_bps`
- `duration_unit`
- `include_benchmark`
- `missing_benchmark_policy`

## Remaining Gaps

1. Relative drawdown expansion (full benchmark episode decomposition) can be enhanced in later slices.

