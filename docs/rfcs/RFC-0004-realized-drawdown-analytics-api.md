# RFC-0004 - Realized Drawdown Analytics API (Industry-Grade, Historical-Only)

- Status: Proposed
- Date: 2026-03-01
- Owners: lotus-risk
- Upstream dependency owners: lotus-performance, lotus-core
- Related:
  - lotus-platform RFC-0067 (API vocabulary and OpenAPI governance)
  - lotus-risk RFC-0002, RFC-0003

## Summary

Introduce a dedicated, production-grade drawdown analytics API in `lotus-risk` for PB/WM usage, focused strictly on current and historical portfolio behavior (no forward-looking forecasts).

The API will provide:

1. Maximum drawdown and full drawdown episode analytics
2. Time-under-water and recovery analytics
3. Path-dependent downside metrics (Ulcer Index, CDaR)
4. Portfolio and optional benchmark-relative drawdown views
5. Stateless and stateful execution modes, consistent with Lotus contracts

## Why This Is Priority #1

Drawdown is the most intuitive downside-risk concept for PB/WM stakeholders (advisors, PMs, CIO, risk, and clients). It directly answers:

1. How much pain did the portfolio experience?
2. How long did it stay underwater?
3. How severe were recurring loss episodes?

Compared with volatility-only reporting, drawdown analytics improves suitability discussions, governance quality, and client communication.

## Industry Research Basis

The design and metric set follow widely used market practices and literature:

1. GIPS standards require maximum drawdown disclosure for fiduciary manager reporting horizons (1/3/5/7/10Y and since inception), reinforcing institutional relevance.
 - Source: GIPS Standards Handbook (Provision 34.A.1)  
   https://www.gipsstandards.org/standards/gips-standards-for-fiduciary-management-providers/gips-standards-handbook-for-fiduciary-management-providers/
2. Maximum drawdown (peak-to-trough) is an industry-standard downside metric and is the de facto risk language in fund/fund-platform reporting.
 - Source: Morningstar glossary (peak-to-trough definition)  
   https://admainnew.morningstar.com/directhelp/Glossary/Custom_Statistics/Maximum_Drawdown.htm
3. Analytical properties of MDD and regime sensitivity are well established in literature.
 - Source: Magdon-Ismail et al., "The Maximum Drawdown of the Brownian Motion"  
   https://authors.library.caltech.edu/records/2aprk-1ee98/latest
4. Conditional drawdown families (CDaR/Conditional Drawdown) are accepted path-dependent downside measures extending beyond single-point MDD.
 - Source: Chekhlov, Uryasev, Zabarankin, "Drawdown Measure in Portfolio Optimization"  
   https://www.researchgate.net/publication/23751240_Drawdown_Measure_in_Portfolio_Optimization

## Problem

`lotus-risk` currently computes a basic drawdown value inside `POST /analytics/risk/calculate`, but does not expose a full drawdown analytics contract suitable for enterprise PB/WM workflows:

1. No episode-level diagnostics (start, trough, recovery, duration)
2. No standardized time-under-water analytics
3. Limited drawdown distribution reporting (top-N/worst episodes)
4. No dedicated, reusable endpoint for downstream consumers (`lotus-report`, `lotus-gateway`, advisory surfaces)

## Goals

1. Deliver a dedicated drawdown API aligned with Lotus mode envelope standards.
2. Keep the implementation strictly historical/current (no predictive analytics).
3. Provide strong quant rigor, transparent formulas, and deterministic behavior.
4. Maintain RFC-0067 compliance (descriptions, examples, vocabulary, no aliases).
5. Provide output consumable by reporting and advisor-facing tools without custom post-processing.

## Non-Goals

1. No forecasted drawdown probabilities.
2. No Monte Carlo or scenario simulation in this RFC.
3. No optimization or auto-rebalancing recommendations.
4. No new portfolio-construction ownership in `lotus-risk`.

## Proposed API

## Endpoint

- `POST /analytics/risk/drawdown`

## Modes

1. `stateless`: caller supplies return series directly.
2. `stateful`: caller supplies identifiers; lotus-risk resolves return series via lotus-performance (`/integration/returns/series`, `core_api_ref`).
3. `simulation`: not in RFC-0004 scope (reserved for later RFC).

## Request Envelope (Canonical)

```json
{
  "input_mode": "stateless | stateful",
  "stateless_input": {},
  "stateful_input": {},
  "analysis_options": {}
}
```

## Stateless Input (v1)

1. `scope`
 - `as_of_date`
 - `reporting_currency` (optional)
 - `net_or_gross`
2. `periods[]`
 - same semantics as risk analytics (`EXPLICIT`, `YTD`, `SI`, etc.)
3. `returns[]`
 - daily/weekly/monthly return observations (percentage points, Lotus canonical)
4. `benchmark_returns[]` (optional)
 - for relative drawdown views

## Stateful Input (v1)

1. `portfolio_id` (required)
2. `as_of_date` (required)
3. `client_id` (optional)
4. `reporting_currency` (optional)
5. `net_or_gross` (default `NET`)
6. `periods[]` (required)
7. `benchmark_policy` (optional; explicit benchmark include/exclude)

## Analysis Options (v1)

1. `include_underwater_series` (default `false`)
2. `include_episode_list` (default `true`)
3. `top_n_episodes` (default `5`, max `50`)
4. `cdar_alpha` (default `0.95`; allowed list in `[0.90, 0.95, 0.99]`)
5. `minimum_episode_depth_bps` (default `0`)
6. `duration_unit` (`BUSINESS_DAYS` default, optional `CALENDAR_DAYS`)

## Response Contract (v1)

```json
{
  "source_service": "lotus-risk",
  "input_mode": "stateful",
  "scope": {
    "as_of_date": "2026-02-28",
    "reporting_currency": "USD",
    "net_or_gross": "NET"
  },
  "results": {
    "YTD": {
      "start_date": "2026-01-01",
      "end_date": "2026-02-28",
      "summary": {
        "max_drawdown": -0.124533,
        "max_drawdown_peak_date": "2026-01-12",
        "max_drawdown_trough_date": "2026-02-03",
        "max_drawdown_recovery_date": null,
        "is_recovered": false,
        "days_to_trough": 16,
        "days_to_recovery": null,
        "time_under_water_days": 34,
        "average_drawdown": -0.041208,
        "ulcer_index": 0.053901,
        "drawdown_at_risk_95": -0.101552,
        "conditional_drawdown_at_risk_95": -0.117884
      },
      "episodes": [
        {
          "episode_id": "dd_0001",
          "peak_date": "2026-01-12",
          "trough_date": "2026-02-03",
          "recovery_date": null,
          "depth": -0.124533,
          "days_to_trough": 16,
          "days_to_recovery": null,
          "total_days": 34,
          "is_recovered": false
        }
      ],
      "relative_to_benchmark": null,
      "underwater_series": null
    }
  },
  "metadata": {
    "contract_version": "v1",
    "rounding_policy_version": "v1",
    "correlation_id": "corr-123"
  }
}
```

## Quantitative Methodology (Normative)

Given cumulative wealth index `W_t`:

1. `W_t = product(1 + r_i)` over period points
2. Running peak `P_t = max(W_0..W_t)`
3. Drawdown series `DD_t = (W_t / P_t) - 1` (<= 0)
4. `max_drawdown = min(DD_t)`
5. Episode segmentation:
 - episode starts when `DD_t` first becomes < 0 after a peak
 - trough is minimum `DD_t` in episode
 - episode recovers when `W_t` >= prior peak
6. `time_under_water`: count of points with `DD_t < 0`
7. `ulcer_index = sqrt(mean(DD_t^2))`
8. `drawdown_at_risk_alpha`: alpha-quantile of episode depths
9. `conditional_drawdown_at_risk_alpha`: mean of worst `(1-alpha)` episode depths

Methodology versioning:

1. Contract carries `methodology_version`.
2. Any material formula change requires version bump and migration note.

## Data and Dependency Contracts

### Upstream

1. `lotus-performance` (primary for stateful):
 - `/integration/returns/series`
 - supports canonical source/provenance and date-windowing
2. `lotus-core` (indirect via lotus-performance `core_api_ref` path):
 - portfolio identity, valuation lineage, baseline data quality ownership

### Downstream

1. `lotus-report` (factsheets, risk dashboards)
2. `lotus-gateway` (platform aggregation)
3. future advisor surfaces (`lotus-advise`, `lotus-manage`) for historical risk diagnostics

## Error and Quality Semantics

Follow existing Lotus error envelope:

1. `INVALID_REQUEST` (schema/validation)
2. `INVALID_INPUT` (business-rule invalidity)
3. `SOURCE_UNAVAILABLE` (upstream failures)
4. `INSUFFICIENT_DATA` (not enough observations)

Quality rules:

1. deterministic results for same inputs
2. consistent timezone/date handling (business-date semantics)
3. explicit missing-data policy propagation from upstream return-series contract
4. no silent fallback for benchmark-relative metrics

## OpenAPI and Vocabulary Governance (RFC-0067)

Mandatory:

1. Full descriptions on all request/response attributes.
2. Realistic examples for each field.
3. Add all new terms to lotus-risk vocabulary inventory.
4. Validate no duplicate/alias terms; use canonical `client_id` terminology.
5. Pass `openapi_quality_gate`, `api_vocabulary_inventory`, and `no_alias_contract_guard`.

## Testing Strategy

1. Unit tests
 - formulas and episode segmentation edge cases
 - open-episode behavior at period end
 - CDaR/DaR quantile math and deterministic rounding
2. Characterization tests
 - known historical paths with locked expected outputs
 - regression snapshots for drawdown episodes
3. Contract tests
 - OpenAPI schema and example conformance
 - error model parity
4. Integration tests
 - stateful path with lotus-performance contract stubs
 - correlation ID and provenance propagation

## Rollout Plan

1. Slice 1:
 - endpoint contract, MDD, episode list, durations, TUW
 - stateless + stateful mode
2. Slice 2:
 - ulcer index, DaR, CDaR
 - benchmark-relative drawdown branch
3. Slice 3:
 - optional underwater series pagination/compression
 - reporting-focused response polish and docs

## Acceptance Criteria

1. All three quality gates pass (OpenAPI, vocabulary, no-alias).
2. Full CI pass including coverage threshold.
3. Backtest/characterization fixtures stable and reviewed.
4. Clear consumer documentation published under `docs/domain-apis/`.
5. No legacy aliases or non-canonical terms.

## Prioritized Backlog (Post RFC-0004 Implementation)

After Realized Drawdown Analytics is fully delivered, execute next initiatives in this order:

1. Rolling Risk Metrics Library
 - rolling volatility, Sharpe, Sortino, beta, TE, IR
 - standardized rolling-window API with reusable contracts
2. Historical Risk Attribution
 - realized risk decomposition by asset class/sector/issuer/currency/position
 - explainability-first outputs for PB/WM reporting
3. Historical Stress Replay
 - historical event windows and shock templates
 - portfolio and segment-level realized shock impact analytics

Each backlog item should have its own RFC and dedicated contract-governance cycle before implementation.

