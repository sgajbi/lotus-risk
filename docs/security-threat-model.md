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
| Oversized POST payload attempts resource exhaustion | `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES` returns `413 PAYLOAD_TOO_LARGE` before handler execution | `test_enterprise_middleware_payload_limit` and `docs/security-deployment-policy.md` | Enterprise deployments must enforce matching ingress and ASGI/server request body limits for requests without trustworthy `Content-Length` |
| Caller invokes calculation POST without actor, tenant, role, or correlation context | `ENTERPRISE_ENFORCE_AUTHZ=true` requires `X-Actor-Id`, `X-Tenant-Id`, `X-Role`, and `X-Correlation-Id`; enterprise runtime enforcement fails startup when authorization is disabled | `test_authorize_write_request_enforces_headers_identity_and_capabilities`, `test_enterprise_middleware_denies_unauthorized_writes`, and `test_validate_enterprise_runtime_config_fails_closed_for_missing_bank_posture` | Local development mode may keep enforcement disabled, but that mode cannot support a bank-buyable production-readiness claim |
| Caller presents actor context without service identity | Authorization fails with `missing_service_identity` unless `X-Service-Identity` or `Authorization` is present | `test_authorize_write_request_enforces_headers_identity_and_capabilities` | Gateway-backed token-validation evidence remains a platform integration proof item |
| Caller lacks endpoint capability or targets an unmapped write path | Well-formed capability rules from `ENTERPRISE_CAPABILITY_RULES_JSON` deny missing `X-Capabilities` entries and unmapped writes fail with `missing_capability_rule` | `test_authorize_write_request_enforces_headers_identity_and_capabilities` | Capability vocabulary and complete write-path mapping must stay governed by deployment configuration |
| Sensitive metadata appears in audit events | `redact_sensitive` masks password, secret, token, authorization, ssn, account_number, and client_email keys recursively | `test_emit_audit_event_redacts_metadata` and `test_redact_sensitive_masks_nested_structures` | Redaction is key-based; newly introduced sensitive field names must update `_REDACT_FIELDS` with tests |
| Downstream service returns unsafe details or malformed payloads | `app.upstream_errors` bounds upstream failure categories and messages | `tests/unit/test_upstream_errors.py` | Upstream contracts must continue publishing bounded problem details |
| Deployment injects a malformed or credential-bearing downstream URL | Shared downstream URL validation permits only valid HTTP(S) service URLs and never echoes rejected values | `tests/unit/test_downstream_base_url.py` and `docs/configuration.md` | Approved endpoint ownership and network egress policy remain deployment responsibilities |
| Metrics cardinality attack through payload fields | Metrics labels are constrained to bounded service/endpoint/status/supportability dimensions | `test_risk_supportability_openapi_documents_metric_labels` | New metrics must use the same bounded-label rule before merge |
| OpenAPI drift hides missing request examples or operation identifiers | `make openapi-gate` evaluates generated schema metadata and request examples; `make openapi-artifact-gate` exports the generated artifact and validates Spectral policy expectations | `tests/unit/test_openapi_quality_gate.py` and `tests/unit/test_openapi_artifact_gate.py` | Keep generated artifact evidence attached to CI/PR review |

## Deployment Decisions

The governed deployment posture is now recorded in
[`security-deployment-policy.md`](security-deployment-policy.md).

1. Local development mode may leave `ENTERPRISE_ENFORCE_AUTHZ` disabled.
2. Enterprise bank deployment mode requires `ENTERPRISE_ENFORCE_AUTHZ=true`.
3. Enterprise bank deployment mode requires `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true`.
4. `ENTERPRISE_PRIMARY_KEY_ID` is required when authorization is enforced.
5. `ENTERPRISE_SECRET_ROTATION_DAYS` must be between `1` and `90`.
6. `ENTERPRISE_CAPABILITY_RULES_JSON` defines endpoint capability requirements.
7. `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES` defines the in-process pre-handler POST payload-size
   threshold.
8. Ingress/proxy and ASGI/server request body limits must be configured at or below
   `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES` for enterprise deployments.
9. Downstream base URLs must be approved HTTP(S) service endpoints without embedded credentials,
   query strings, fragments, whitespace, or control characters.
10. Enterprise runtime enforcement fails application construction when required in-process bank
    configuration is absent or invalid.

## Evidence Commands

Use these commands as focused security evidence for the refactor PR:

```text
python -m pytest tests/unit/test_enterprise_readiness.py tests/unit/test_upstream_errors.py tests/unit/test_security_evidence_docs.py -q
python -m pytest tests/unit/test_enterprise_deployment_policy_docs.py -q
make security-audit
make lint
make typecheck
```

## Follow-Up Backlog

1. Add gateway-backed token-validation evidence when platform identity contracts are available.
2. Attach generated OpenAPI artifact evidence to the final PR.
3. Validate the final enterprise deployment configuration in the target runtime before merge or
   release promotion.
