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
- Version metadata: /version
- Ops diagnostics: /ops

`/metadata` and `/version` return the same build provenance block:

1. Git commit SHA.
2. Git branch or ref.
3. Build timestamp.
4. Repository URL.
5. Image digest.
6. CI pipeline/run ID.

The Docker image carries the matching OCI labels for commit SHA, branch/ref, build timestamp,
source repository URL, image digest field, and CI run ID. The final registry digest must be supplied
by publish/deployment metadata through `LOTUS_IMAGE_DIGEST`; a local unpublished build cannot embed
its own final digest as a build-time label because the label changes the digest.

`/health/ready` and `/ops` publish configured-only dependency rows by default. A row with
`status: "configured"` and `detail: "configured_only_no_probe"` means the dependency base URL is
configured and source-safe to display; it does not prove `lotus-core` or `lotus-performance`
reachability. Reachability and data-contract failures are proven by endpoint-level downstream
errors, `metadata.calculation_supportability`, upstream request metrics, and explicit runtime
dependency status overrides when an operator or higher-level runtime has injected them.

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
6. Verify `ENTERPRISE_INGRESS_MAX_BODY_BYTES` and `ENTERPRISE_ASGI_MAX_BODY_BYTES` are set to the
   effective configured limits. Startup issue codes `missing_or_invalid_ingress_max_body_bytes`,
   `missing_or_invalid_asgi_max_body_bytes`, `ingress_max_body_bytes_exceeds_app_limit`, and
   `asgi_max_body_bytes_exceeds_app_limit` mean the deployment cannot claim bank readiness.
7. Treat missing body-limit enforcement for requests without trustworthy `Content-Length` as a
   deployment-readiness failure, not an application-code exception.
8. Verify `ENTERPRISE_TRUSTED_INGRESS_SECRET` is set and that gateway/ingress strips caller-supplied
   `X-Lotus-Trusted-Ingress`, validates caller token and operator access, then injects the trusted
   marker. `missing_trusted_ingress_secret` means the service must not be promoted as bank-ready.
9. Confirm `/ops`, `/ops/trust-telemetry`, and `/metrics` return `403 AUTHORIZATION_DENIED` without
   the trusted-ingress marker in enterprise mode while `/health`, `/health/live`, and
   `/health/ready` remain available for platform probes.
10. Verify `LOTUS_CORE_BASE_URL` and `LOTUS_PERFORMANCE_BASE_URL` are explicit approved service
   endpoints.
11. Verify explicit `LOTUS_CORE_*`, `LOTUS_PERFORMANCE_*`, and `LOTUS_PERFORMANCE_ASYNC_*` timeout,
   pool, keepalive, and polling overrides are positive numeric controls. In enterprise mode,
   `invalid_downstream_runtime_setting:<ENV_NAME>` means a configured runtime control is malformed
   or nonpositive; fix the configuration rather than relying on local fallback defaults.
12. Treat any `enterprise_runtime_config_invalid:<issue-codes>` startup failure as a blocked
   deployment until every bounded issue code is resolved.
13. Confirm `/openapi.json` shows `x-lotus-enterprise-authorization` on every supported analytics
   write operation before publishing generated client or QA evidence.

## Endpoint Failure Rate Alert

Alert id: `lotus-risk-endpoint-failure-rate`

1. Inspect `lotus_risk_endpoint_executions_total` grouped by `endpoint` and `input_mode`.
2. Check whether failures are isolated to `stateful`, `stateless`, or `simulation` workflows.
3. Treat failures as final endpoint-response failures: they include service-operation exceptions
   and response-model validation or serialization failures before endpoint success is recorded.
4. Use the request correlation ID from the client error response or logs for request-level tracing.
5. If failures are stateful only, continue with the upstream dependency checks below.

## Upstream Dependency Failure Alert

Alert id: `lotus-risk-upstream-dependency-failures`

1. Inspect `lotus_risk_upstream_requests_total` grouped by `dependency`, `operation`, and
   `category`.
2. For `timeout` or `transport`, verify network path, DNS, and service readiness for `lotus-core`
   and `lotus-performance`.
3. For `data_gap` or `invalid_response`, compare the failing operation with
   `docs/domain-apis/risk-upstream-failure-behavior.md`.
4. Confirm retry behavior and timeout posture before escalating to the upstream owning team.

Bounded upstream operation values are:

| Dependency | Operation | First diagnostic check | Escalation |
| --- | --- | --- | --- |
| `lotus-core` | `/simulation-sessions` | Verify concentration simulation request shape, idempotency context, and lotus-core simulation-session readiness. | `lotus-core` simulation/session owner |
| `lotus-core` | `/simulation-sessions/{session_id}/changes` | Verify idempotency key, change-set fingerprint, and session version posture. | `lotus-core` simulation/session owner |
| `lotus-core` | `/integration/portfolios/{portfolio_id}/core-snapshot` | Verify portfolio snapshot availability and source portfolio readiness. | `lotus-core` portfolio snapshot owner |
| `lotus-core` | `/integration/instruments/enrichment-bulk` | Verify instrument authority/enrichment coverage for requested securities. | `lotus-core` instrument reference owner |
| `lotus-core` | `/integration/portfolios/{portfolio_id}/analytics/position-timeseries` | Verify position analytics history coverage and grouping support. | `lotus-core` analytics input owner |
| `lotus-core` | `/integration/reference/risk-free-series` | Verify reporting currency, date window, and risk-free source coverage. | `lotus-core` reference data owner |
| `lotus-core` | `/integration/reference/risk-free-series/coverage` | Verify currency coverage and date-window availability; currency must not appear in the metric label. | `lotus-core` reference data owner |
| `lotus-performance` | `/integration/returns/series` | Verify return-series request shape, benchmark/risk-free selection, and async accepted payload posture. | `lotus-performance` returns owner |
| `lotus-performance` | `/integration/returns/series/status/{calculation_id}` | Verify async execution status and polling budget; calculation ID must not appear in the metric label. | `lotus-performance` returns async owner |
| `lotus-performance` | `/integration/returns/series/results/{calculation_id}` | Verify async result availability and accepted `202`/`404` pending posture. | `lotus-performance` returns async owner |
| `lotus-performance` | `/integration/benchmarks/exposure-context` | Verify benchmark exposure context coverage for the requested grouping dimension. | `lotus-performance` benchmark exposure owner |

Do not add concrete portfolio IDs, simulation IDs, currency query strings, or async calculation IDs
to `lotus_risk_upstream_requests_total.operation`. Add new runtime operations through
`src/app/integrations/upstream_operations.py`, the monitoring contract, focused validator tests, and
this runbook together.

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
2. Verify `/health/ready` and `/ops` for service readiness, draining posture, and configured-only
   dependency rows; use upstream request metrics and endpoint errors to distinguish live dependency
   failures from application failures.
3. Check recent deploy and configuration changes, including enterprise authorization settings.
4. Run `make check` locally for fast reproduction and `make ci` before opening a hotfix PR.
