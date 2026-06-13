# Validation and CI

## Lane Model

`lotus-risk` follows the Lotus CI lane model:

1. `Remote Feature Lane`
2. `Pull Request Merge Gate`
3. `Main Releasability Gate`

The repo-native commands are designed to map to those lanes directly.

## Primary Commands

- `make check` - fast local gate
- `make ci` - PR-grade local gate
- `make quality-baseline` - report-only enterprise refactor baseline and quality scorecard
- `make mesh-contract-validate` - domain product, trust telemetry, and observability contract validation
- `make domain-data-product-gate` - repo-native domain product declaration validation
- `make openapi-gate` - generated schema quality
- `make openapi-artifact-gate` - generated artifact policy
- `make api-vocabulary-gate` - API vocabulary inventory validation
- `make test-unit` - unit suite
- `make test-integration` - integration suite
- `make test-e2e` - e2e suite
- `make migration-apply` - migration contract check
- `make docker-build` - Docker build validation

## What `make check` Protects

`make check` currently covers:

1. lint,
2. no-alias governance,
3. typecheck,
4. OpenAPI quality,
5. API vocabulary validation,
6. mesh contract validation,
7. source-size regression protection,
8. unit-focused default test execution.

## What `make ci` Adds

`make ci` is the local PR-grade gate. It adds:

1. migration smoke,
2. test-pyramid validation,
3. security audit,
4. split unit, integration, and e2e suites,
5. coverage enforcement,
6. Docker build validation.

## Quality Baseline

`make quality-baseline` generates report-only refactor evidence under `quality/`.

It currently records:

1. largest files and functions/classes,
2. API entry-point modularity risk,
3. architecture and API-governance rules,
4. quality scorecard posture,
5. report-only import-linter/Spectral readiness.

This evidence is a prioritization and regression-control baseline. It is not an enterprise-readiness
completion claim until the progressive gates move from report-only to enforced thresholds.

## Why These Gates Matter Here

In `lotus-risk`, the gates protect more than code style.

They protect:

1. domain vocabulary consistency,
2. no-alias API discipline,
3. product-surface semantic correctness,
4. evidence-backed supportability claims,
5. dependency-aware runtime posture.

## Validation Sources

- `Makefile`
- `REPOSITORY-ENGINEERING-CONTEXT.md`
- `quality/baseline_report.md`
- `quality/quality_scorecard.md`
- `docs/operations/development-workflow-and-ci-strategy.md`
- `docs/domain-apis/endpoint-matrix.md`
- `docs/domain-apis/risk-product-surface-alignment.md`

The active `make source-size-gate` prevents new Python source monoliths above the governed
450-line ceiling. It runs in local `make check`/`make ci` and the Feature, PR Merge, and Main
Releasability lanes.

## Read Next

1. use [Development Workflow](./Development-Workflow.md) for the repo loop,
2. use [Troubleshooting](./Troubleshooting.md) when a gate fails for a non-obvious reason,
3. use [Operations Runbook](./Operations-Runbook.md) when the failure is really an upstream/runtime issue.
