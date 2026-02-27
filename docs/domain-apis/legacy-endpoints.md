# Legacy Endpoint Assessment

## Endpoint

- `POST /analytics/workbench/risk-proxy`

## Current Status

- Removed from runtime route surface.
- Requests now return `404` with platform error envelope.

## Rationale

- Endpoint name encoded a downstream UI context (`workbench`) and did not align with lotus-risk bounded-context vocabulary.
- Canonical concentration route is `POST /analytics/risk/concentration`.
