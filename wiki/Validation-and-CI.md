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
6. unit-focused default test execution.

## What `make ci` Adds

`make ci` is the local PR-grade gate. It adds:

1. migration smoke,
2. test-pyramid validation,
3. security audit,
4. split unit, integration, and e2e suites,
5. coverage enforcement,
6. Docker build validation.

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
- `docs/operations/development-workflow-and-ci-strategy.md`
- `docs/domain-apis/endpoint-matrix.md`
- `docs/domain-apis/risk-product-surface-alignment.md`

## Read Next

1. use [Development Workflow](./Development-Workflow.md) for the repo loop,
2. use [Troubleshooting](./Troubleshooting.md) when a gate fails for a non-obvious reason,
3. use [Operations Runbook](./Operations-Runbook.md) when the failure is really an upstream/runtime issue.
