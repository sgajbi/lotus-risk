# Service Operations Runbook

## Standard Commands

- `make check` for the fast local gate.
- `make ci` for the PR-grade local gate.
- `make mesh-contract-validate` for domain product, trust telemetry, and observability contract
  validation.
- `docker compose up --build` for prod-shaped local runtime.
- `docker compose down` to stop the local runtime.

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
4. Check `/integration/capabilities` before treating an unsupported mode as an outage.
5. For stateful-only failures, validate `LOTUS_CORE_BASE_URL` and `LOTUS_PERFORMANCE_BASE_URL`
   before changing analytics code.

## Enterprise Deployment Security Checks

Enterprise bank deployments must run with the security posture in
`docs/security-deployment-policy.md`.

1. Verify `ENTERPRISE_ENFORCE_AUTHZ=true`.
2. Verify `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true`.
3. Verify `ENTERPRISE_PRIMARY_KEY_ID` and `ENTERPRISE_SECRET_ROTATION_DAYS` are set.
4. Verify `ENTERPRISE_CAPABILITY_RULES_JSON` contains the endpoint capability map for write-like
   analytics POST endpoints and that no supported write path is unmapped. Startup now enforces this:
   `missing_capability_rule:<METHOD> <PATH>` means a published write route is not covered. A prefix
   rule such as `"POST /analytics/risk": "risk.analytics.write"` is valid when the deployment wants
   one common analytics-write capability.
5. Verify ingress/proxy and ASGI/server request body limits are at or below
   `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES`.
6. Treat missing body-limit enforcement for requests without trustworthy `Content-Length` as a
   deployment-readiness failure, not an application-code exception.
7. Verify `LOTUS_CORE_BASE_URL` and `LOTUS_PERFORMANCE_BASE_URL` are explicit approved service
   endpoints.
8. Treat any `enterprise_runtime_config_invalid:<issue-codes>` startup failure as a blocked
   deployment until every bounded issue code is resolved.
9. Confirm `/openapi.json` shows `x-lotus-enterprise-authorization` on every supported analytics
   write operation before publishing generated client or QA evidence.

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

The service owns reusable `lotus-core` and `lotus-performance` HTTP pools for the FastAPI lifespan.
During shutdown it reports draining posture and closes those pools. Repeated connection setup under
normal runtime traffic indicates the service was started without ASGI lifespan support.

## Calculation Supportability Alert

Alert id: `lotus-risk-calculation-supportability-degraded`

1. Inspect `lotus_risk_calculation_supportability_total` grouped by `operation`,
   `supportability_state`, and `reason`.
2. Use response `metadata.calculation_supportability` for the same bounded state and reason without
   exposing portfolio or client identifiers in metrics.
3. For `stale_source_observations`, validate source freshness from upstream dependency diagnostics.
4. For `permission_blocked`, verify caller capability and deployment authorization policy.

## Escalation Paths

Escalate by ownership boundary:

1. `lotus-risk` owner: calculation defects, supportability metadata, risk methodology, OpenAPI,
   capability publication, and bounded risk error mapping.
2. `lotus-performance` owner: returns, benchmark returns, benchmark exposure context, and
   performance-aligned attribution inputs.
3. `lotus-core` owner: portfolio snapshots, simulation sessions, instrument enrichment, issuer
   authority, and risk-free reference series.
4. `lotus-gateway` owner: client-facing composition, entitlement propagation, and downstream
   contract preservation.
5. `lotus-platform` owner: ingress, CI governance, mesh certification, wiki sync automation, and
   shared observability contracts.

Do not reclassify an unsupported workflow as degraded. Unsupported modes should remain deterministic
request-validation or capability-publication outcomes.

## HTTP 5xx Alert

Alert id: `lotus-risk-http-5xx`

1. Inspect `http_requests_total` grouped by `handler` and `status`.
2. Verify `/health/ready` and `/ops` to distinguish dependency degradation from application
   failures.
3. Check recent deploy and configuration changes, including enterprise authorization settings.
4. Run `make check` locally for fast reproduction and `make ci` before opening a hotfix PR.
