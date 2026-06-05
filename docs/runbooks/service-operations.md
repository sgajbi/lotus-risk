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

## Enterprise Deployment Security Checks

Enterprise bank deployments must run with the security posture in
`docs/security-deployment-policy.md`.

1. Verify `ENTERPRISE_ENFORCE_AUTHZ=true`.
2. Verify `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true`.
3. Verify `ENTERPRISE_PRIMARY_KEY_ID` and `ENTERPRISE_SECRET_ROTATION_DAYS` are set.
4. Verify `ENTERPRISE_CAPABILITY_RULES_JSON` contains the endpoint capability map for write-like
   analytics POST endpoints.
5. Verify ingress/proxy and ASGI/server request body limits are at or below
   `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES`.
6. Treat missing body-limit enforcement for requests without trustworthy `Content-Length` as a
   deployment-readiness failure, not an application-code exception.

## Endpoint Failure Rate Alert

Alert id: `lotus-risk-endpoint-failure-rate`

1. Inspect `lotus_risk_endpoint_executions_total` grouped by `endpoint` and `input_mode`.
2. Check whether failures are isolated to `stateful`, `stateless`, or `simulation` workflows.
3. Use the request correlation ID from the client error response or logs for request-level tracing.
4. If failures are stateful only, continue with the upstream dependency checks below.

## Upstream Dependency Failure Alert

Alert id: `lotus-risk-upstream-dependency-failures`

1. Inspect `lotus_risk_upstream_requests_total` grouped by `dependency`, `operation`, and
   `category`.
2. For `timeout` or `transport`, verify network path, DNS, and service readiness for `lotus-core`
   and `lotus-performance`.
3. For `data_gap` or `invalid_response`, compare the failing operation with
   `docs/domain-apis/risk-upstream-failure-behavior.md`.
4. Confirm retry behavior and timeout posture before escalating to the upstream owning team.

## Calculation Supportability Alert

Alert id: `lotus-risk-calculation-supportability-degraded`

1. Inspect `lotus_risk_calculation_supportability_total` grouped by `operation`,
   `supportability_state`, and `reason`.
2. Use response `metadata.calculation_supportability` for the same bounded state and reason without
   exposing portfolio or client identifiers in metrics.
3. For `stale_source_observations`, validate source freshness from upstream dependency diagnostics.
4. For `permission_blocked`, verify caller capability and deployment authorization policy.

## HTTP 5xx Alert

Alert id: `lotus-risk-http-5xx`

1. Inspect `http_requests_total` grouped by `handler` and `status`.
2. Verify `/health/ready` and `/ops` to distinguish dependency degradation from application
   failures.
3. Check recent deploy and configuration changes, including enterprise authorization settings.
4. Run `make check` locally for fast reproduction and `make ci` before opening a hotfix PR.
