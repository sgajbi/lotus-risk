# Security and Governance

## Governance Posture

For `lotus-risk`, governance is mainly about analytical truth, contract discipline, and clear
upstream authority boundaries.

The important rules are:

1. do not broaden workflow support beyond what the contract declares,
2. do not hide supportability gaps behind generic UI wording,
3. do not let downstream consumers silently change risk meaning,
4. keep upstream authority lines explicit between `lotus-risk`, `lotus-core`, and `lotus-performance`.

## Core Contract Rules

The highest-value rules for this repo are:

1. signed VaR and expected shortfall semantics must be preserved,
2. attribution reconciliation fields must stay attached to contributor outputs,
3. stateful issuer active-risk must remain backed by lotus-performance benchmark exposure context issuer groups,
4. simulation must remain concentration-only,
5. lineage and upstream request-fingerprint metadata must survive downstream shaping.

## API Governance

`lotus-risk` is under strong contract governance:

1. no-alias rules are enforced,
2. OpenAPI quality is enforced,
3. API vocabulary validation is enforced,
4. test-pyramid discipline is enforced,
5. standard error responses preserve the Lotus `error.code` envelope and also publish additive
   RFC 7807/problem-details fields inside the same `error` object,
6. security audit and Docker build are part of the real CI contract.

## Enterprise Deployment Security

Bank deployment mode is stricter than local development mode:

1. `ENTERPRISE_ENFORCE_AUTHZ=true` is required,
2. `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true` is required,
3. `ENTERPRISE_PRIMARY_KEY_ID`, `ENTERPRISE_SECRET_ROTATION_DAYS`, and
   `ENTERPRISE_CAPABILITY_RULES_JSON` must be configured,
4. ingress/proxy and ASGI/server request body limits must be aligned to
   `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES`,
5. gateway or platform ingress validates token integrity while `lotus-risk` enforces required
   actor, tenant, role, correlation, service identity, and capability evidence.
6. caller-provided correlation and trace headers are untrusted: unsafe or unbounded correlation IDs
   and malformed, zero, or mismatched W3C trace context are replaced rather than reflected or
   logged.
7. client-facing upstream failure envelopes preserve bounded dependency and retry context but never
   expose raw downstream response bodies or transport exception text.
8. every API response is marked `no-store`, `no-referrer`, and `nosniff`, including early
   authorization and payload-limit failures.
9. downstream base URLs fail fast unless they are valid HTTP(S) service endpoints without embedded
   credentials, query strings, fragments, whitespace, or control characters.
10. `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true` fails service construction unless the documented
    in-process bank posture is complete; failures expose bounded issue codes, not values.
11. authorization-enforced write paths without a well-formed matching capability rule fail closed
    with `missing_capability_rule`.
12. enterprise body-limit proof is executable: `ENTERPRISE_INGRESS_MAX_BODY_BYTES` and
    `ENTERPRISE_ASGI_MAX_BODY_BYTES` must prove external limits are present and no larger than the
    in-process application limit.
13. direct local Uvicorn/Compose runtime is local-only for body-limit posture unless an approved
    deployment supplies the machine-readable proof values.
14. write requests, `/ops`, `/ops/trust-telemetry`, and `/metrics` require trusted-ingress proof in
    enterprise mode; `/health`, `/health/live`, and `/health/ready` remain available for platform
    probes.
15. the gateway or ingress must strip caller-supplied `X-Lotus-Trusted-Ingress` and inject it only
    after token and operator-access validation.

## Upstream Boundary Discipline

`lotus-risk` must not absorb authority that belongs elsewhere.

Keep these lines clear:

1. `lotus-performance` owns performance returns and benchmark exposure context,
2. `lotus-core` owns snapshot, enrichment, simulation, and reference contracts,
3. `lotus-risk` owns the risk analytics semantics and outputs built from those inputs.

## Supportability Truth

A feature being implemented is not the same as a feature being broadly supportable.

Current examples:

1. historical attribution exists with issuer active-risk support; broader live archetype evidence remains intentionally scoped,
2. live validation exists, but enterprise archetype breadth is still limited,
3. concentration simulation is real, but simulation support does not generalize to the rest of the service.

## Source Documents

- `docs/domain-apis/risk-product-surface-alignment.md`
- `docs/domain-apis/endpoint-matrix.md`
- `docs/standards/risk-analytics-contract.md`
- `docs/standards/platform-compliance-assessment.md`
- `docs/security-deployment-policy.md`

## Read Next

1. use [Integrations](./Integrations.md) for the downstream contract view,
2. use [RFC Index](./RFC-Index.md) for the local decision trail,
3. use [Roadmap](./Roadmap.md) for the remaining supportability gaps.
