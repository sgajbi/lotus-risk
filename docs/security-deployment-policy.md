# Lotus Risk Enterprise Deployment Security Policy

This document records the governed deployment posture for `lotus-risk`. It is a production-readiness
policy for existing enterprise-readiness controls and the bounded verified-principal pilot.
Configuration alone does not certify production IAM or bank readiness.

## Verified-Principal Pilot

Set `LOTUS_RISK_PRINCIPAL_POSTURE=verified` at application construction. The deployment composition
must inject `PrincipalProviders` through `create_app`: a credential verifier and a live GrantStore.
The supplied `Ed25519CredentialVerifier` requires explicit issuer, audience, deployment-trusted JWKS,
revocation provider and clock. No provider, membership or grant is inferred from caller data.

Only concentration, regime-scenario-pack evaluation and risk-event affected-cohort evaluation are
admitted in this posture. Other protected writes, scenario jobs and operator routes fail closed;
health probes remain available. This is not a full-service authentication rollout.

The verifier checks strict compact JWS framing, unique JSON members, EdDSA/Ed25519 signatures,
issuer, audience, integer expiry/not-before, principal kind and revocation. Membership and configured
route capabilities are resolved from GrantStore. Delegated capabilities and portfolio scope are the
intersection of user and application grants; every named portfolio must be entitled before engine
or downstream execution. Header actor, tenant, role and capabilities cannot supply authority.
Correlation remains diagnostic. Missing providers return bounded denial, never header fallback.

`header-trust` is retained only for explicit `local` or `dev` environments selected by
`LOTUS_RISK_DEPLOYMENT_ENVIRONMENT` (default `local`). Other environments reject header-trust at
construction. Operators must declare the real deployment environment; a default is not evidence of
deployment classification. Existing enterprise ingress, payload and image controls remain necessary
but do not certify trusted key custody, revocation availability or production GrantStore operation.

Evidence: `tests/integration/test_verified_risk_authority_http.py` exercises actual loopback HTTP,
real signatures, three financial engines, all thirteen refusal classes and concurrent synthetic
tenant isolation. It does not establish a live Manage-to-Risk exchange. Keep [Risk #384](https://github.com/sgajbi/lotus-risk/issues/384)
and the consumer-owned integration acceptance separate from production IAM approval.

## Deployment Modes

| Mode | Purpose | Required posture |
| --- | --- | --- |
| Local development | Fast local service execution, isolated tests, and contract generation | `ENTERPRISE_ENFORCE_AUTHZ` may remain unset or `false`; local callers may use test headers |
| Enterprise bank deployment | Any shared, client-facing, gateway-connected, or bank evaluation environment | `ENTERPRISE_ENFORCE_AUTHZ=true` and `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true` are required |

Enterprise bank deployment requirements below are baseline controls, not a production-readiness
verdict. Local development mode is intentionally not a production security posture.

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

## Retained Header-Trust Boundary (Local/Dev Only)

`lotus-risk` is not the platform identity provider. The retained compatibility path behaves as follows;
it is not admission evidence for the verified-principal pilot:

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
   inventory, and blocking scans for every HIGH/CRITICAL finding complete before registry
   authentication or publication,
5. any HIGH/CRITICAL finding fails the applicable blocking scan and prevents publication,
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

The builder uses `pip` to install the application, but the final runtime stage removes that package
manager after copying installed dependencies. Its build-time import guard also rejects a retained
`pip` module. The standard-library `ensurepip` bootstrap and its bundled wheel are also removed,
and the build guard rejects a retained bootstrap so the runtime user cannot reinstall bundled pip.
Removal and verification run with isolated Python startup (`-I -S`) and inspect resolved standard-
library and installation paths. Runtime `sitecustomize`/`usercustomize` modules and site-packages
`.pth` files are rejected so they cannot activate hidden package paths or executable startup code
outside those inspected roots. Existing file-backed entries on the isolated interpreter's default
import path are also rejected, preventing sibling zip archives from supplying hidden modules.
Builder output is limited to `/install/bin` and the Python 3.12 site-packages tree before it is
copied over `/usr/local`; output that could replace standard-library files is refused. It also
cannot contain a `python*` executable collision, and removal/verification invokes the base image's
versioned interpreter path. The release build is pinned to repository context `.`, the validated
root `Dockerfile`, and the `runtime` target; custom Dockerfile syntax frontends and the external
`BUILDKIT_SYNTAX` frontend selector are forbidden. Release build arguments must match the complete
approved provenance contract, so runtime expression indirection cannot inject additional arguments.
The approved build action is unique, and later build or local-tag mutation commands are forbidden. The
approved build's immutable local image ID is captured immediately; SBOM and vulnerability scans use
that ID, and publication refuses a tag that no longer resolves to it. The
builder and runtime stages, including each direct
base image and logical instruction sequence, are contract-locked so package stashes cannot be added
outside the reviewed install/removal path. The validated `runtime` stage must remain the final
Dockerfile stage because the release build publishes Docker's default final target.
The final-image vulnerability inventory, not the Dockerfile alone, is the evidence
that HIGH/CRITICAL package findings are absent; local image proof does not certify a published release.

### Base-image vulnerability treatment

All Docker stages use the same approved, immutable Python 3.12 Alpine 3.23 index digest. The runtime
stage applies available operating-system updates during the build. The release workflow then scans
the exact captured final-image ID before registry authentication or publication.

The governed Trivy HIGH/CRITICAL vulnerability scan preserves a complete SARIF inventory and
independently blocks every application-library and operating-system finding at those severities.
The release contract forbids `ignore-unfixed`:
absence of a published fix does not convert a terminal vulnerability verdict into release
acceptance. Base-image digest changes require a reviewed contract update, a real image build, and a
fresh exact-image scan. SBOM, signature, provenance attestation, and immutable digest evidence remain
required but do not override a failed vulnerability gate.

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
