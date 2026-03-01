# lotus-core and lotus-performance Requirements for Historical Attribution Integration

## Scope

This document defines the upstream contracts required by `lotus-risk` to support:

- `POST /analytics/risk/historical-attribution`
- `input_mode=stateful` (v1)

This is aligned with RFC-0006 and RFC-0067 governance.

## Ownership Boundaries (Non-Negotiable)

1. `lotus-performance` is the system of record for historical return series:
- portfolio returns
- benchmark returns

2. `lotus-core` is the system of record for canonical domain/master data:
- position history and market values
- instrument metadata and issuer hierarchy
- security classification dimensions

3. `lotus-risk` only computes risk attribution. It must not reconstruct master data that belongs to `lotus-core` or return series that belongs to `lotus-performance`.

## Required Upstream Contracts

### A) lotus-performance (Required)

Endpoint:

- `POST /integration/returns/series`

Purpose:

- return aligned historical return series for the requested portfolio scope.

Minimum request contract expected by lotus-risk:

```json
{
  "portfolio_id": "PORT_ABC_001",
  "as_of_date": "2026-02-28",
  "window": { "mode": "RELATIVE", "period": "SI" },
  "frequency": "DAILY",
  "metric_basis": "NET",
  "reporting_currency": "USD",
  "series_selection": {
    "include_portfolio": true,
    "include_benchmark": true,
    "include_risk_free": false
  },
  "data_policy": {
    "missing_data_policy": "ALLOW_PARTIAL",
    "fill_method": "NONE",
    "calendar_policy": "BUSINESS"
  },
  "input_mode": "stateful",
  "stateful_input": {
    "consumer_system": "lotus-risk"
  }
}
```

Minimum response contract required:

```json
{
  "series": {
    "portfolio_returns": [
      { "date": "2026-01-02", "return_value": "0.0015" }
    ],
    "benchmark_returns": [
      { "date": "2026-01-02", "return_value": "0.0011" }
    ],
    "risk_free_returns": []
  },
  "alignment": {
    "start_date": "2026-01-02",
    "end_date": "2026-02-28"
  },
  "metadata": {
    "source_system": "lotus-performance",
    "contract_version": "v1"
  }
}
```

Required behavior:

1. Portfolio returns must always be present for successful stateful attribution.
2. Benchmark returns are required when `ACTIVE_RISK` or `TRACKING_ERROR` attribution is requested.
3. `return_value` must be decimal return (not percentage); lotus-risk converts to internal risk units.
4. All rows must use ISO date format and deterministic ordering.
5. Correlation ID must be propagated end-to-end.

### B) lotus-core (Required)

Endpoint 1:

- `POST /integration/portfolios/{portfolio_id}/analytics/position-timeseries`

Purpose:

- return position-by-date exposure base used for attribution grouping and weights.

Minimum request contract expected by lotus-risk:

```json
{
  "as_of_date": "2026-02-28",
  "window": {
    "start_date": "2026-01-02",
    "end_date": "2026-02-28"
  },
  "frequency": "daily",
  "dimensions": ["sector", "asset_class"],
  "reporting_currency": "USD",
  "consumer_system": "lotus-risk",
  "page": {
    "page_size": 5000,
    "page_token": null
  }
}
```

Minimum response contract required:

```json
{
  "rows": [
    {
      "valuation_date": "2026-01-02",
      "security_id": "SEC_AAPL_US",
      "ending_market_value_reporting_currency": "150000.00",
      "ending_market_value_portfolio_currency": "150000.00",
      "dimensions": {
        "sector": "Information Technology",
        "asset_class": "Equity"
      }
    }
  ],
  "page": {
    "next_page_token": null
  },
  "metadata": {
    "source_system": "lotus-core",
    "contract_version": "v1"
  }
}
```

Required behavior:

1. `rows[]` must be returned for each available valuation date in window.
2. At least one of:
- `ending_market_value_reporting_currency`
- `ending_market_value_portfolio_currency`
   must be populated per row.
3. Stable pagination contract using `page.next_page_token`.
4. `dimensions` keys must be canonical and stable (`sector`, `asset_class`).
5. Correlation ID must be propagated end-to-end.

Endpoint 2:

- `POST /integration/instruments/enrichment-bulk`

Purpose:

- map `security_id` to issuer hierarchy for `grouping_dimension=ISSUER`.

Minimum request contract:

```json
{
  "security_ids": ["SEC_AAPL_US", "SEC_MSFT_US"]
}
```

Minimum response contract:

```json
{
  "records": [
    {
      "security_id": "SEC_AAPL_US",
      "issuer_id": "ISSUER_APPLE_INC",
      "issuer_name": "Apple Inc.",
      "ultimate_parent_issuer_id": "ISSUER_APPLE_HOLDCO",
      "ultimate_parent_issuer_name": "Apple HoldCo"
    }
  ]
}
```

Required behavior:

1. Records may omit unknown securities, but response shape must remain valid.
2. `issuer_id` and `issuer_name` must be deterministic for a given `security_id`.
3. Correlation ID must be propagated end-to-end.

## Capability Matrix for Historical Attribution

1. `TOTAL_RISK + VOLATILITY` stateful:
- needs `portfolio_returns` from lotus-performance
- needs position timeseries + dimensions from lotus-core

2. `ACTIVE_RISK + TRACKING_ERROR` stateful:
- needs `portfolio_returns` and `benchmark_returns` from lotus-performance
- needs portfolio exposure timeseries from lotus-core
- needs benchmark exposure timeseries contract (currently gap if not yet available)

3. `grouping_dimension=ISSUER`:
- needs instrument enrichment-bulk from lotus-core

4. `grouping_dimension=POSITION | SECTOR | ASSET_CLASS`:
- no issuer enrichment required

## Gaps to Resolve (if not already live)

1. Benchmark exposure history contract for active attribution in stateful mode:
- required to fully support `ACTIVE_RISK` decomposition by grouping dimension.

2. Explicit response metadata in both upstream services:
- lineage and contract version fields should be stable and documented.

3. OpenAPI completeness:
- all request/response attributes must include descriptions and realistic examples per RFC-0067.

## Non-Functional Requirements

1. Determinism:
- same request produces same results and ordering.

2. Performance:
- support at least 5,000 rows per page in `position-timeseries`.

3. Resilience:
- standard Lotus error envelope, clear message, correlation ID echo.

4. Governance:
- canonical snake_case only; no legacy aliases.
- all attributes must exist in API vocabulary inventory.

## Acceptance Checklist

1. Stateful `TOTAL_RISK` attribution succeeds end-to-end using upstream data only.
2. Stateful `ACTIVE_RISK` attribution succeeds end-to-end when benchmark exposure history is available.
3. `ISSUER` grouping succeeds with enrichment-bulk.
4. Contract tests validate required fields and type/shape guarantees.
5. Characterization tests lock numerical behavior for stable fixtures.
6. OpenAPI docs include full descriptions and realistic examples for all attributes.
