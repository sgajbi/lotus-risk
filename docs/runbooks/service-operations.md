# Service Operations Runbook

## Standard Commands

- make lint
- make typecheck
- make ci
- docker compose up --build

## Health and Readiness

- Liveness: /health/live
- Readiness: /health/ready
- General health: /health
- Metadata: /metadata
- Ops diagnostics: /ops

## Incident First Checks

1. Check container logs for request failures and stack traces.
2. Verify /health/ready, /ops, and metrics endpoint.
3. Run local parity check (make ci) before hotfix PR.
