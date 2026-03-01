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

- Status: not implemented in lotus-risk.
- Target behavior:
  - caller supplies identifiers (`portfolioId`, optional `cifId`, `period`, options).
  - lotus-risk sources required series internally from Lotus services and computes.

### Simulation

- Status: not implemented in lotus-risk.
- Target behavior:
  - lotus-risk sources baseline state from upstream.
  - caller provides scenario/override deltas.
  - service computes adjusted risk analytics.

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

## Stateful/Simulation Input Source Mapping (Target)

| Input Needed | Preferred Source App | Availability | Notes |
|---|---|---|---|
| Portfolio baseline snapshot (`portfolioId`, holdings, valuation context) | lotus-core (`/integration/portfolios/{id}/core-snapshot`) | Exists | Already used by other services. |
| Raw valuation/performance input points | lotus-core (`/integration/portfolios/{id}/performance-input`) | Exists | Provides valuation points and metadata. |
| Daily return series normalized for risk engine | lotus-performance (`/performance/twr` or PAS-input flows) or lotus-risk-internal derivation | Partial | lotus-risk has no internal sourcing path today. |
| Benchmark return series | lotus-performance / market data integration | Needs enhancement | no direct lotus-risk-managed benchmark source contract today. |
| Simulation projected positions/summary | lotus-core simulation APIs (`/simulation-sessions/*/projected-*`) | Exists | currently consumed via gateway patterns, not lotus-risk. |
| Scenario overrides schema | lotus-risk-owned request contract | Needs enhancement | no simulation contract yet in lotus-risk. |

## Expected Output Structure

- `scope` (echoed normalized request scope)
- `results` map keyed by period name/type:
  - `startDate`
  - `endDate`
  - `metrics` map:
    - each metric:
      - `value: float | null`
      - `details?: object`
        - deterministic error object on metric-level failure (`details.error`)
        - metric-specific detail payload (for example drawdown metadata, VaR expected shortfall)

## Alignment Assessment

- Bounded context ownership: aligned (`lotus-risk` is correct owner per RFC-0065).
- API mode support: partial (stateless only).
- Cross-service integration posture: downstream-ready; upstream sourcing not yet integrated in-service.
- Naming/vocabulary: largely aligned in current stateless contract.

## Gaps and Decisions Required

1. Define a stateful request contract for this endpoint (or separate endpoint) with identifiers and policy context.
2. Decide authoritative internal data path for returns generation:
   - compute inside lotus-risk from core performance-input
   - or rely on lotus-performance return service as an upstream dependency.
3. Define benchmark sourcing contract and ownership for stateful/simulation modes.
4. Define simulation override schema and merge semantics.
5. Standardize response metadata additions (for example `correlationId`, `contractVersion`, `asOfDate`) if this endpoint must fully match cross-platform response envelope conventions.
