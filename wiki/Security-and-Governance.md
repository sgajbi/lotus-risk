# Security and Governance

## Governance Map

Current scope: this page summarizes implementation-backed security, deployment, and governance
posture for `lotus-risk`. It does not claim full bank production approval beyond the executable
controls and evidence paths listed here.

| Area | Current evidence | Operator action |
| --- | --- | --- |
| Enterprise runtime mode | `docs/security-deployment-policy.md` and startup validation tests | Configure required bank-mode environment and trusted-ingress proof |
| Image supply chain | `make image-supply-chain-gate` and `.github/workflows/image-release.yml` | Promote the same signed digest across environments |
| API governance | no-alias, OpenAPI, vocabulary, and test-pyramid gates | Keep downstream risk semantics aligned to source contracts |

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

## Image Supply Chain

Release images are governed by the same security posture as runtime configuration:

1. CI is the only image-push path, through `.github/workflows/image-release.yml`;
2. images are tagged with the Git SHA and labeled with commit, branch/ref, service version, build
   timestamp, repository URL, image digest field, and CI run ID;
3. the release workflow builds locally, generates SBOM plus complete HIGH/CRITICAL SARIF evidence,
   and completes a blocking scan for fixable HIGH/CRITICAL findings before registry authentication
   or image publication;
4. only a scan-passing image is pushed, after which the registry digest is signed, attested, and
   recorded in `image-release-manifest.json`;
5. Kubernetes and Helm manifests must deploy by `image@sha256:<digest>`;
6. environment promotion must reuse the same digest instead of rebuilding per environment;
7. Docker build arguments and environment declarations must not carry secret-like names or values;
8. the production `runtime` target installs the package non-editably from a separate builder stage,
   applies current operating-system security updates, runs as the non-root `lotus` user at UID/GID
   `10001`, excludes repository `scripts/`, copies the governed domain-data-product declarations
   beneath `LOTUS_REPO_ROOT=/app`, and declares a `/health/ready` container healthcheck.

`/version` exposes the runtime service version and the same source/build/image/CI metadata expected
on the released image. `make image-supply-chain-gate` is the local and CI guard for this contract,
including the enforced scan-before-publication sequence and hardened runtime-target contract. The
deployable runtime image installs runtime dependencies only and rejects dev tooling during the Docker
build if pytest, ruff, mypy, bandit, deptry, radon, vulture, or pre-commit are present.

After the full SARIF inventory is written, a library-only scan blocks every application dependency
HIGH/CRITICAL finding, including findings without a published fix. The separate OS-only scan uses
`ignore-unfixed: true`; this keeps every newly fixable base-image HIGH/CRITICAL finding
release-blocking while retaining visibility of Debian findings that have no published remediation.
The OS-only posture is owned by `lotus-risk` maintainers and expires on 2026-09-30. The repository gate enforces
`UNFIXED_VULNERABILITY_EXCEPTION_EXPIRES_ON` and fails after that date unless maintainers renew it
from a fresh image scan.

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

1. use [Integrations](Integrations) for the downstream contract view,
2. use [RFC Index](RFC-Index) for the local decision trail,
3. use [Roadmap](Roadmap) for the remaining supportability gaps.
