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
8. Any explicit downstream timeout, connection-pool, keepalive, or async polling override must be
   a positive finite numeric value for seconds-based settings and a positive integer for count-based
   settings.
9. `ENTERPRISE_INGRESS_MAX_BODY_BYTES` and `ENTERPRISE_ASGI_MAX_BODY_BYTES` set to the effective
   ingress/proxy and ASGI/server body limits for the deployment.
10. `ENTERPRISE_TRUSTED_INGRESS_SECRET` set to the secret value injected by the approved gateway or
    ingress after caller/token/operator validation.

The service must fail closed when these requirements are missing in enterprise mode. Runtime
configuration validation in `src/app/enterprise_readiness.py` enforces the in-process portion of
this policy. When `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true`, service construction fails unless
authorization is enabled and policy version, key ID, rotation days, positive payload limit, and both
upstream base URLs are explicit. It also rejects malformed, zero, negative, or non-finite explicit
downstream runtime overrides with bounded
`invalid_downstream_runtime_setting:<ENV_NAME>` issue codes and rejects missing trusted-ingress
proof with `missing_trusted_ingress_secret`. Capability rules are required as nonempty string mappings.
They must cover every supported write-like analytics route published by the service:

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
2. The approved gateway or ingress strips any caller-supplied `X-Lotus-Trusted-Ingress` header and
   injects that header only after caller credential, token-integrity, and operator-access checks.
3. `lotus-risk` rejects write-like analytics requests and protected operational endpoints unless
   `X-Lotus-Trusted-Ingress` matches `ENTERPRISE_TRUSTED_INGRESS_SECRET`.
4. `lotus-risk` requires actor, tenant, role, correlation, and service identity evidence on
   write-like analytics requests.
5. `lotus-risk` validates configured endpoint capability requirements against the caller capability
   header.
6. Correlation and trace identifiers support observability and auditability, but they are never
   authorization proof.

The trusted-ingress secret is service-owned proof that direct clients cannot authorize writes or
operator diagnostics by supplying only actor, tenant, role, service identity, and capability headers.
It is not a substitute for gateway token validation; it is the app-side enforcement point that proves
the gateway token-validation evidence boundary is present before the service trusts propagated caller
context.

Generated OpenAPI documents this conditional enterprise caller-context contract through the
`x-lotus-enterprise-authorization` extension on supported write-like analytics operations. The
extension lists required context headers, service identity header alternatives, the capabilities
header, the capability-rule environment variable, and the bounded 403 denial code.

## Protected Operational Endpoints

Enterprise mode protects operator-only diagnostics and metrics through the same trusted-ingress
marker:

1. `GET /ops`,
2. `GET /ops/trust-telemetry`,
3. `GET /metrics`.

Health and readiness probes remain available without the trusted-ingress marker so platform
orchestrators can continue liveness and readiness checks. The protected endpoints remain source-safe,
but source-safe does not mean public.

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
4. Set `ENTERPRISE_INGRESS_MAX_BODY_BYTES` and `ENTERPRISE_ASGI_MAX_BODY_BYTES` to the effective
   configured limits so startup can verify both external limits are present and no larger than the
   in-process application limit.
5. Treat a missing ingress/server body-limit configuration as a production-readiness failure.

Enterprise runtime validation rejects missing, malformed, zero, negative, or oversized external
body-limit proof with bounded issue codes:

1. `missing_or_invalid_ingress_max_body_bytes`,
2. `missing_or_invalid_asgi_max_body_bytes`,
3. `ingress_max_body_bytes_exceeds_app_limit`,
4. `asgi_max_body_bytes_exceeds_app_limit`.

The repository `Dockerfile` and `docker-compose.yml` run plain Uvicorn directly for local developer
and contract-test workflows. That direct Compose path is not enterprise body-limit proof unless a
deployment supplies the explicit proof variables above from an approved ingress/proxy and ASGI/server
configuration.

## Image Supply Chain And Promotion

Release images must be built, scanned, signed, attested, and pushed by CI only. Developer machines
may build local images for validation, but local images are not release artifacts and must not be
promoted to bank or shared environments.

The governed release image policy is:

1. release images are tagged with the Git commit SHA,
2. OCI labels include commit SHA, Git branch/ref, service version, UTC build timestamp, repository
   URL, image digest field, and CI pipeline/run ID,
3. image push is permitted only through `.github/workflows/image-release.yml`,
4. the image is built and loaded locally so an SPDX SBOM, a complete HIGH/CRITICAL vulnerability
   inventory, and the blocking scan for fixable HIGH/CRITICAL findings complete before registry
   authentication or publication,
5. a fixable HIGH/CRITICAL finding fails the blocking scan and prevents publication,
6. after the scan passes, the immutable image is pushed and its registry digest is captured in
   `output/image-release/image-release-manifest.json`,
7. the image is signed by digest with keyless cosign signing,
8. provenance attestation is generated and pushed for the image digest,
9. Kubernetes and Helm deployment manifests must reference images by `image@sha256:<digest>`, not
   mutable tags,
10. `/version` exposes the service version plus the same commit, branch, build timestamp, repository
    URL, image digest, and CI run metadata carried by the image labels and runtime environment,
11. environment promotion must reuse the same image digest across environments instead of rebuilding
    per environment,
12. Docker `ARG` and `ENV` declarations must not expose secrets, tokens, passwords, private keys, or
    credentials. Use CI secret stores, deployment secret stores, or BuildKit secret mounts rather
    than baking secret names or values into the image,
13. the deployable `runtime` target must be a non-editable installed package copied from a separate
    builder stage, apply current operating-system security updates, run as the non-root `lotus` user
    at UID/GID `10001`, omit repository `scripts/`, include the governed domain-data-product
    declarations under the explicit `LOTUS_REPO_ROOT`, and expose a `/health/ready` container
    healthcheck.

`make image-supply-chain-gate` is the repository-native guard for these requirements. It validates
the build, SBOM, blocking scan, registry authentication, publication, signing, and attestation
order; validates required Docker metadata; enforces the multi-stage, installed-package, non-root,
healthchecked runtime target with its required data-product declarations; blocks image push outside
the image-release workflow; rejects mutable
Kubernetes image references and secret-like Docker build argument or environment names; and verifies
that pytest, ruff, mypy, bandit, deptry, radon, vulture, and pre-commit are absent from the deployable
runtime image.

### Unfixed base-image vulnerability treatment

The complete Trivy SARIF inventory intentionally retains HIGH/CRITICAL findings regardless of fix
availability. A separate application-library scan blocks every HIGH/CRITICAL finding, including
findings without a published fix. The OS-only blocking scan uses `ignore-unfixed: true`; it
suppresses only base-image findings for which the vulnerability feed publishes no fixed version,
while every fixable OS HIGH/CRITICAL finding remains release-blocking. This is an actionability rule,
not a severity downgrade or a package-specific ignore list.

The governed Trivy HIGH/CRITICAL vulnerability scan therefore has three evidence-preserving passes:
complete SARIF visibility, an unconditional application-library gate, and the expiring OS-only
fixable-finding gate.

| Control field | Governed value |
|---|---|
| Owner | `lotus-risk` maintainers |
| Reason | Debian base-image findings without an upstream fixed version cannot be remediated by this repository; blocking them would permanently disable signing and attestation without reducing risk. |
| Review trigger | Every image build, base-image digest change, or vulnerability-database change; newly fixable findings fail the release automatically. |
| Expiry | 2026-09-30; encoded by `UNFIXED_VULNERABILITY_EXCEPTION_EXPIRES_ON`; the repository gate fails after this date unless maintainers renew it with a fresh scan and explicit evidence. |
| Compensating evidence | Complete SARIF inventory, SPDX SBOM, immutable digest, signature, provenance attestation, and fixable-finding blocking scan. |

## Evidence Commands

Use these commands for focused local evidence after changing enterprise deployment posture:

```text
make image-supply-chain-gate
python -m pytest tests/unit/test_enterprise_readiness.py tests/unit/test_security_evidence_docs.py tests/unit/test_enterprise_deployment_policy_docs.py -q
python -m pytest tests/unit/test_openapi_quality_gate.py tests/integration/test_health.py -q
make security-audit
make lint
make typecheck
```
