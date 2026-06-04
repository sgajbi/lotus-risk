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
