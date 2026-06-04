# Lotus Risk Security Threat Model And Abuse-Control Evidence

This document records the current enterprise security posture for `lotus-risk` risk analytics
endpoints. It is evidence for the enterprise refactor PR and must stay aligned with
`src/app/enterprise_readiness.py`, `src/app/middleware/correlation.py`, `src/app/upstream_errors.py`,
and the repository security gates.

## Scope

`lotus-risk` exposes read-only operational endpoints and write-like POST analytics endpoints for
front-office risk calculation workflows. The service processes portfolio identifiers, positions,
returns, benchmark references, simulation identifiers, and supportability metadata. The service must
not leak client-sensitive values through logs, metrics, errors, OpenAPI examples, operational
diagnostics, or downstream failure messages.

## Assets

| Asset | Security expectation | Current evidence |
| --- | --- | --- |
| Portfolio and benchmark identifiers | Treat as client-sensitive operational data | Correlation, audit, and metrics rules forbid request/response payload labels |
| Request and response payloads | Never log raw payloads or expose payload fields as metric labels | `redact_sensitive` coverage and RFC-0108 supportability label tests |
| Actor, tenant, role, and service identity headers | Required when enterprise write authorization is enabled | `authorize_write_request` and enterprise middleware tests |
| Correlation and trace identifiers | Propagate for supportability, but do not treat as authorization proof | Correlation middleware and error-envelope tests |
| Downstream errors from `lotus-core` and `lotus-performance` | Map to bounded platform error envelopes | `app.upstream_errors` unit coverage |
| OpenAPI examples and operational docs | Use canonical non-secret examples only | `make openapi-gate` and request-example validation tests |
| Python dependencies | Audit the isolated project dependency graph, not global developer packages | `make security-audit` via `scripts/dependency_health_check.py --skip-outdated` |

## Trust Boundaries

1. External caller or `lotus-gateway` to `lotus-risk` HTTP API.
2. `lotus-risk` routers to service/use-case modules.
3. `lotus-risk` service modules to downstream adapters for `lotus-core` and `lotus-performance`.
4. Middleware and diagnostics to logs, metrics, and error envelopes.
5. Generated OpenAPI and documentation to client-visible contract artifacts.

## Abuse Cases And Controls

| Abuse case | Current control | Verification evidence | Remaining risk |
| --- | --- | --- | --- |
| Oversized POST payload attempts resource exhaustion | `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES` returns `413 PAYLOAD_TOO_LARGE` before handler execution | `test_enterprise_middleware_payload_limit` | Streaming/body-size enforcement depends on upstream ASGI/server configuration for requests without trustworthy `Content-Length` |
| Caller invokes calculation POST without actor, tenant, role, or correlation context | `ENTERPRISE_ENFORCE_AUTHZ=true` requires `X-Actor-Id`, `X-Tenant-Id`, `X-Role`, and `X-Correlation-Id` | `test_authorize_write_request_enforces_headers_identity_and_capabilities` and `test_enterprise_middleware_denies_unauthorized_writes` | Enforcement remains environment-controlled until final enterprise readiness mode is selected |
| Caller presents actor context without service identity | Authorization fails with `missing_service_identity` unless `X-Service-Identity` or `Authorization` is present | `test_authorize_write_request_enforces_headers_identity_and_capabilities` | Token validation is delegated to gateway/platform identity infrastructure |
| Caller lacks endpoint capability | Capability rules from `ENTERPRISE_CAPABILITY_RULES_JSON` deny missing `X-Capabilities` entries | `test_authorize_write_request_enforces_headers_identity_and_capabilities` | Capability vocabulary must be governed by deployment configuration |
| Sensitive metadata appears in audit events | `redact_sensitive` masks password, secret, token, authorization, ssn, account_number, and client_email keys recursively | `test_emit_audit_event_redacts_metadata` and `test_redact_sensitive_masks_nested_structures` | Redaction is key-based; newly introduced sensitive field names must update `_REDACT_FIELDS` with tests |
| Downstream service returns unsafe details or malformed payloads | `app.upstream_errors` bounds upstream failure categories and messages | `tests/unit/test_upstream_errors.py` | Upstream contracts must continue publishing bounded problem details |
| Metrics cardinality attack through payload fields | Metrics labels are constrained to bounded service/endpoint/status/supportability dimensions | `test_risk_supportability_openapi_documents_metric_labels` | New metrics must use the same bounded-label rule before merge |
| OpenAPI drift hides missing request examples or operation identifiers | `make openapi-gate` evaluates generated schema metadata and request examples | `tests/unit/test_openapi_quality_gate.py` | Secondary Spectral artifact export remains a PR-readiness follow-up |

## Deployment Decisions

1. `ENTERPRISE_ENFORCE_AUTHZ` controls write-authorization enforcement.
2. `ENTERPRISE_ENFORCE_RUNTIME_CONFIG` converts runtime configuration findings into startup
   failures.
3. `ENTERPRISE_PRIMARY_KEY_ID` is required when authorization is enforced.
4. `ENTERPRISE_SECRET_ROTATION_DAYS` must be between 1 and 90.
5. `ENTERPRISE_CAPABILITY_RULES_JSON` defines endpoint capability requirements.
6. `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES` defines the pre-handler POST payload-size threshold.

## Evidence Commands

Use these commands as focused security evidence for the refactor PR:

```text
python -m pytest tests/unit/test_enterprise_readiness.py tests/unit/test_upstream_errors.py tests/unit/test_security_evidence_docs.py -q
make security-audit
make lint
make typecheck
```

## Follow-Up Backlog

1. Promote final enterprise readiness mode once deployment identity validation is settled.
2. Add gateway-backed token-validation evidence when platform identity contracts are available.
3. Add server-level request body limits for requests without trustworthy `Content-Length`.
4. Standardize secondary Spectral OpenAPI artifact export in CI.
