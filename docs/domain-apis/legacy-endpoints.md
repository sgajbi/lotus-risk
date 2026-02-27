# Legacy Endpoint Assessment

## Endpoint

- `POST /analytics/workbench/risk-proxy`

## Purpose

- Backward-compatible alias for workbench risk proxy payloads.
- Internally routes to the same concentration calculation path as `/analytics/risk/concentration`.

## Visibility

- Hidden from OpenAPI (`include_in_schema=False`).

## Alignment Assessment

- Positive:
  - useful for short-term compatibility while consumers migrate.
- Concern:
  - endpoint name embeds downstream (`workbench`) context into `lotus-risk` public surface.
  - this is not ideal long-term bounded-context vocabulary.

## Dependency Notes

- Active consumer:
  - `lotus-gateway` workbench service via `PaClient.get_workbench_risk_proxy`.

## Decision Required

1. Keep as compatibility endpoint with explicit sunset date.
2. Or remove once gateway migrates to `/analytics/risk/concentration`.
3. If kept temporarily, publish deprecation metadata in response headers or capability docs.

## Recommendation (Analysis)

- Maintain temporarily for stability, but treat as deprecation track item and migrate gateway to canonical concentration endpoint.
