# lotus-core Requirements for Issuer Concentration Integration

## Scope

This document defines the upstream contract requirements from lotus-core needed by lotus-risk issuer concentration analytics.

## Required capabilities

### 1) Core snapshot enrichment

Endpoint:

- `POST /integration/portfolios/{portfolio_id}/core-snapshot`

Required addition in `sections.instrument_enrichment[]` rows:

1. `issuer_id`
2. `issuer_name`
3. `ultimate_parent_issuer_id`
4. `ultimate_parent_issuer_name`

Existing fields (`security_id`, `isin`, `asset_class`, `sector`, `country_of_risk`, `instrument_name`) remain unchanged.

### 2) Stateless enrichment fallback

New/extended integration endpoint for bulk instrument enrichment by security list:

- `POST /integration/instruments/enrichment-bulk`

Request:

```json
{
  "security_ids": ["SEC_AAPL_US", "SEC_MSFT_US"]
}
```

Response:

```json
{
  "records": [
    {
      "security_id": "SEC_AAPL_US",
      "issuer_id": "ISSUER_APPLE_INC",
      "issuer_name": "Apple Inc.",
      "ultimate_parent_issuer_id": "ISSUER_APPLE_HOLDING",
      "ultimate_parent_issuer_name": "Apple Holdings PLC"
    }
  ]
}
```

Behavior:

1. Unknown securities may be omitted or returned with null issuer fields.
2. Endpoint must be deterministic for same input set.
3. Must include standard Lotus error envelope and correlation propagation.

## Non-functional requirements

1. OpenAPI and examples must satisfy RFC-0067 quality gates.
2. API vocabulary inventory entries must be added for new issuer attributes.
3. No aliases; canonical snake_case only.
4. Backward compatibility for existing consumers must be preserved.

## Vocabulary additions expected in lotus-platform inventory

1. `issuer_id`
2. `issuer_name`
3. `ultimate_parent_issuer_id`
4. `ultimate_parent_issuer_name`
5. `security_ids` (bulk enrichment request field)

## Validation checklist after core implementation

1. Stateful concentration call returns issuer concentration with `coverageStatus=complete`.
2. Simulation concentration call returns issuer concentration with `coverageStatus=complete`.
3. Stateless with `enrichmentPolicy=merge_caller_then_core` enriches missing mappings from core bulk endpoint.
4. Stateless with `enrichmentPolicy=core_only` uses only core mappings.
5. Stateless with `enrichmentPolicy=use_caller_only` does not call core enrichment endpoint.
