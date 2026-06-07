# Lotus Risk Operations Runbook

## Local Commands

1. Install: `make install`
2. Fast gate: `make check`
3. PR-grade gate: `make ci`
4. Quality baseline: `make quality-baseline`
5. Domain data product gate: `make domain-data-product-gate`

## Operational Endpoints

1. `/health`
2. `/health/live`
3. `/health/ready`
4. `/metadata`
5. `/ops`
6. `/metrics`

## Refactor Operating Notes

Quality baseline updates are report-only until thresholds are agreed and the largest route/service
modules are split. Do not treat generated quality reports as enterprise-readiness proof by
themselves; they are evidence for prioritization and regression control.

## Enterprise Deployment Security

Bank deployment mode requires the posture in `docs/security-deployment-policy.md`: authorization
enforcement, runtime configuration enforcement, explicit key and secret-rotation configuration,
endpoint capability rules, and ingress/server request body limits aligned to
`ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES`.

## Downstream Connection Pools

FastAPI lifespan startup owns one reusable HTTP connection pool for `lotus-core` and one for
`lotus-performance`. Pool limits, keepalive limits, keepalive expiry, and request timeout are
configured through the dependency-specific environment variables documented in
`docs/domain-apis/risk-upstream-failure-behavior.md`.

On shutdown, the service enters draining posture before closing its owned downstream pools.
