# Risk Calculation Endpoint Assessment

## Endpoint

- `POST /analytics/risk/calculate`

## Purpose

- Compute portfolio risk metrics (volatility, drawdown, Sharpe, Sortino, beta, tracking error, information ratio, VaR) across configured periods.

## Execution Mode Support

### Stateless

- Status: supported now.
- Behavior:
  - caller provides full return series and options in payload.
  - service computes without internal upstream data retrieval.

### Stateful

- Status: implemented in lotus-risk.
- Current behavior:
  - caller supplies identifiers plus risk metric specification (`periods`, `metrics`, `options`).
  - lotus-risk sources canonical return series from `lotus-performance` using `input_mode=stateful` and `stateful_input is an empty envelope; consumer identity is stamped by lotus-performance server-side`.
  - lotus-risk computes with the same risk engine used by stateless mode.

### Simulation

- Status: intentionally unsupported in the current production contract.
- Reason:
  - current metric set is primarily realized historical-return analytics
  - a projected holdings snapshot does not produce a valid realized return history for these metrics

## Stateless Inputs (Current)

- `input_mode: "stateless"` (required in this slice)
- `stateless_input.scope`
  - `as_of_date: date`
  - `reporting_currency?: str`
  - `net_or_gross: "NET" | "GROSS"`
- `stateless_input.periods[]`
  - `type: EXPLICIT|YEAR|MTD|QTD|YTD|ONE_YEAR|THREE_YEAR|FIVE_YEAR|SI`
  - `name?: str`
  - `from_date?/to_date?` (required for `EXPLICIT`)
  - `year?` (required for `YEAR`)
- `stateless_input.metrics[]`
  - `VOLATILITY|DRAWDOWN|SHARPE|SORTINO|BETA|TRACKING_ERROR|INFORMATION_RATIO|VAR`
- `stateless_input.options`
  - frequency/log-return/risk-free/MAR/annualization/benchmark/VaR method config
- `stateless_input.portfolio_open_date: date`
- `stateless_input.returns[]: [{date, value}]`
- `stateless_input.benchmark_returns[]: [{date, value}]` (required for benchmark-dependent metrics)

## Stateful/Simulation Input Source Mapping (Current + Target)

| Input Needed | Preferred Source App | Availability | Notes |
|---|---|---|---|
| Portfolio baseline snapshot (`portfolioId`, holdings, valuation context) | lotus-core (`/integration/portfolios/{id}/core-snapshot`) | Exists | Already used by other services. |
| Raw valuation/performance input points | lotus-core (`/integration/portfolios/{id}/performance-input`) | Exists | Provides valuation points and metadata. |
| Daily return series normalized for risk engine | lotus-performance (`/integration/returns/series` with `input_mode=stateful`) | Exists | Implemented stateful path in lotus-risk; decimal returns converted to percentage-point risk engine input. |
| Benchmark return series | lotus-performance / market data integration | Needs enhancement | no direct lotus-risk-managed benchmark source contract today. |
## Expected Output Structure

- `scope` (echoed normalized request scope)
- `metadata`
  - `contract_version`
  - `methodology_version`
  - applied frequency / annualization / log-return / risk-free / VaR settings
- `results` map keyed by period name/type:
  - `start_date`
  - `end_date`
  - `portfolio_observation_count`
  - `benchmark_observation_count`
  - `aligned_benchmark_observation_count`
  - `benchmark_context` (`requested`, `available`, `aligned`, `reason`, `requested_metric_count`)
  - `metrics` map:
    - each metric:
      - `value: float | null`
      - `details?: object`
        - deterministic error object on metric-level failure (`details.error`)
        - metric-specific detail payload (for example drawdown metadata, VaR expected shortfall)

## Alignment Assessment

- Bounded context ownership: aligned (`lotus-risk` is correct owner per RFC-0065).
- API mode support: finalized for current scope (`stateless` + `stateful` only; `simulation` intentionally unsupported).
- Cross-service integration posture: integrated with `lotus-performance` for stateful return sourcing.
- Naming/vocabulary: aligned with canonical `client_id` naming and RFC-0067 guardrails.

## Gaps and Decisions Required

1. Benchmark/risk-free sourcing remains upstream-dependent on lotus-performance + lotus-core reference-data availability; stateful benchmark metrics degrade deterministically when benchmark series is absent, and this is now surfaced in `benchmark_context.reason`.
2. Standardize response metadata additions (for example `correlationId`, `contractVersion`, `asOfDate`) if this endpoint must fully match cross-platform response envelope conventions.

