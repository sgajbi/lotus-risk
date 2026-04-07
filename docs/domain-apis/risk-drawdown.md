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
  - `portfolio_observation_count`
  - `benchmark_observation_count`
  - `summary` (max drawdown, timing, TUW, ulcer, DaR/CDaR)
  - `episodes[]` (top-N worst by depth)
  - `relative_to_benchmark` (optional; active drawdown depth plus timing/recovery fields)
- `relative_to_benchmark_context` (requested/applied/aligned-observation status)
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

## Business Interpretation Notes

- `max_drawdown = 0.0` means the realized wealth path never fell below its in-period running peak. This is a valid outcome, not missing data.
- `relative_to_benchmark` is computed on the active return path `(portfolio - benchmark)`, not on the benchmark standalone wealth path.
- `relative_to_benchmark_context.applied = false` means the caller asked for benchmark-relative drawdown but lotus-risk did not have aligned benchmark observations for that period.
- `relative_to_benchmark_context.reason` explains why relative drawdown was or was not computed:
  - `NOT_REQUESTED`
  - `BENCHMARK_UNAVAILABLE`
  - `NO_ALIGNED_OBSERVATIONS`
  - `APPLIED`
- `portfolio_observation_count` and `benchmark_observation_count` show how much realized history supported the period result and should be checked before over-interpreting short windows.
- `time_under_water_days` counts observations below the running peak. It is a persistence signal, not simply the gap between peak and trough dates.
- `is_recovered = false` means the path had not returned to its prior peak by period end. In that case `max_drawdown_recovery_date` and `days_to_recovery` remain `null`.
- `episodes[]` is filtered by `minimum_episode_depth_bps` and truncated by `top_n_episodes`, so it is a ranked decision support view rather than a full event ledger unless the caller requests it that way.

## Example Use

- Private banker review:
  - use `summary.max_drawdown`, `summary.time_under_water_days`, and `summary.is_recovered` to judge whether the client experienced a meaningful realized loss and whether it recovered quickly.
- Benchmark-relative review:
  - use `relative_to_benchmark.max_drawdown` and `relative_to_benchmark.time_under_water_days` to judge whether underperformance was both deep and persistent.
- QA / operations:
  - use `metadata` to confirm whether benchmark-relative drawdown, underwater series, and episode filters were actually applied.

## Remaining Gaps

1. Relative drawdown expansion (full benchmark episode decomposition) can be enhanced in later slices.

