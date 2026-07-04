# Lotus Risk Enterprise Deployment Security Policy

This document records the governed deployment posture for `lotus-risk`. It is a production-readiness
policy for how the existing enterprise-readiness controls must be configured in bank or enterprise
environments. It does not change local developer defaults.

## Deployment Modes

| Mode | Purpose | Required posture |
| --- | --- | --- |
| Local development | Fast local service execution, isolated tests, and contract generation | `ENTERPRISE_ENFORCE_AUTHZ` may remain unset or `false`; local callers may use test headers |
| Enterprise bank deployment | Any shared, client-facing, gateway-connected, or bank evaluation environment | `ENTERPRISE_ENFORCE_AUTHZ=true` and `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true` are required |

Enterprise bank deployment mode is the only mode that supports a bank-buyable production-readiness
claim. Local development mode is intentionally not a production security posture.

## Required Enterprise Configuration

Enterprise bank deployments must provide all of the following:

1. `ENTERPRISE_ENFORCE_AUTHZ=true`
2. `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true`
3. `ENTERPRISE_PRIMARY_KEY_ID` set to the active key identifier used for audit and rotation
   evidence.
4. `ENTERPRISE_SECRET_ROTATION_DAYS` set between `1` and `90`.
5. `ENTERPRISE_CAPABILITY_RULES_JSON` configured with endpoint capability requirements for
   write-like analytics POST endpoints.
6. `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES` set explicitly and aligned to ingress and ASGI/server body
   limits.
7. `LOTUS_CORE_BASE_URL` and `LOTUS_PERFORMANCE_BASE_URL` set to approved HTTP(S) service
   endpoints without embedded credentials, query strings, or fragments.

The service must fail closed when these requirements are missing in enterprise mode. Runtime
configuration validation in `src/app/enterprise_readiness.py` enforces the in-process portion of
this policy. When `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true`, service construction fails unless
authorization is enabled and policy version, key ID, rotation days, positive payload limit, and both
upstream base URLs are explicit. Capability rules are required as nonempty string mappings and must
cover every supported write-like analytics route published by the service:

1. `POST /analytics/risk/calculate`,
2. `POST /analytics/risk/concentration`,
3. `POST /analytics/risk/drawdown`,
4. `POST /analytics/risk/historical-attribution`,
5. `POST /analytics/risk/mandate-health-context`,
6. `POST /analytics/risk/regime-scenario-pack/evaluate`,
7. `POST /analytics/risk/risk-event-cohorts/evaluate`,
8. `POST /analytics/risk/rolling-metrics`.

Every authorization-enforced write path must match a well-formed write-method capability rule before
enterprise application construction succeeds. Prefix rules remain supported, so
`"POST /analytics/risk": "risk.analytics.write"` can cover the full current analytics surface.
Unmapped writes fail startup with `missing_capability_rule:<METHOD> <PATH>`, and overlapping
prefixes resolve to the most specific path rule at request time.

## Identity Boundary

`lotus-risk` is not the platform identity provider. In enterprise deployment mode:

1. `lotus-gateway` or the platform ingress layer validates caller credentials and token integrity.
2. `lotus-risk` requires actor, tenant, role, correlation, and service identity evidence on
   write-like analytics requests.
3. `lotus-risk` validates configured endpoint capability requirements against the caller capability
   header.
4. Correlation and trace identifiers support observability and auditability, but they are never
   authorization proof.

Gateway-backed token-validation evidence remains a platform integration proof item. It is not a
reason to leave `lotus-risk` authorization enforcement disabled in an enterprise deployment.

Generated OpenAPI documents this conditional enterprise caller-context contract through the
`x-lotus-enterprise-authorization` extension on supported write-like analytics operations. The
extension lists required context headers, service identity header alternatives, the capabilities
header, the capability-rule environment variable, and the bounded 403 denial code.

## Request Body Limits

`ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES` protects the FastAPI application from oversized write-like
requests when `Content-Length` is present and trustworthy. Enterprise deployments must also enforce
the same or lower maximum body size at the ingress/proxy and ASGI/server layer so streaming or
chunked requests without trustworthy `Content-Length` are rejected before unbounded application
buffering can occur.

The production deployment checklist is:

1. Configure ingress/proxy maximum request body size at or below `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES`.
2. Configure ASGI/server request body limits where the selected server supports them.
3. Keep `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES` explicit in the service environment.
4. Treat a missing ingress/server body-limit configuration as a production-readiness failure.

## Evidence Commands

Use these commands for focused local evidence after changing enterprise deployment posture:

```text
python -m pytest tests/unit/test_enterprise_readiness.py tests/unit/test_security_evidence_docs.py tests/unit/test_enterprise_deployment_policy_docs.py -q
python -m pytest tests/unit/test_openapi_quality_gate.py tests/integration/test_health.py -q
make security-audit
make lint
make typecheck
```
