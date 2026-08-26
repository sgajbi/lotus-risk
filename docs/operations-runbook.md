# Lotus Risk Operations Runbook

## Local Commands

1. Install: `make install`
2. Fast gate: `make check`
3. PR-grade gate: `make ci`
4. Quality baseline: `make quality-baseline`
5. Domain data product gate: `make domain-data-product-gate`
6. Isolated container gate: `make ci-local-docker`
7. Isolated container cleanup: `make ci-local-docker-down`

The CI-local Compose lifecycle derives a stable project name from the checkout path. Its `up` and
`down` commands therefore affect only that checkout's test containers, network, and volumes; they
must not remove the separately running product Compose project. Set `CI_LOCAL_COMPOSE_PROJECT` only
when an operator needs an explicit, equally isolated namespace.

## Operational Endpoints

1. `/health`
2. `/health/live`
3. `/health/ready`
4. `/metadata`
5. `/version`
6. `/ops`
7. `/metrics`

## Refactor Operating Notes

Quality baseline updates are report-only until thresholds are agreed and the largest route/service
modules are split. Do not treat generated quality reports as enterprise-readiness proof by
themselves; they are evidence for prioritization and regression control.

## Enterprise Deployment Security

Bank deployment mode requires the posture in `docs/security-deployment-policy.md`: authorization
enforcement, runtime configuration enforcement, explicit key and secret-rotation configuration,
endpoint capability rules, and ingress/server request body limits aligned to
`ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES`. Enterprise startup also requires
`ENTERPRISE_INGRESS_MAX_BODY_BYTES` and `ENTERPRISE_ASGI_MAX_BODY_BYTES` to prove the effective
external limits are present and no larger than the in-process write payload limit. Protected
operator endpoints and write requests require the trusted-ingress marker injected by the approved
gateway or ingress from `ENTERPRISE_TRUSTED_INGRESS_SECRET`; health probes remain available without
that marker.

## Downstream Connection Pools

FastAPI lifespan startup owns one reusable HTTP connection pool for `lotus-core` and one for
`lotus-performance`. Pool limits, keepalive limits, keepalive expiry, and request timeout are
configured through the dependency-specific environment variables documented in
`docs/domain-apis/risk-upstream-failure-behavior.md`.

On shutdown, the service enters draining posture before closing its owned downstream pools.
