# Development Workflow

## Start Here

Current-state workflow guidance: use the smallest repo-native proof that covers the slice, then move
to PR-grade validation when contracts, runtime posture, release evidence, or supportability truth
changes.

| Change type | First local proof | Escalate before PR |
| --- | --- | --- |
| Endpoint, contract, or analytics behavior | `make check` | `make ci` |
| Runtime, Docker, or release metadata | `make image-supply-chain-gate` and `make docker-build` | `make ci` |
| Documentation or wiki truth | focused docs tests or wiki audit | `make check` |

## Working Model

Use a small, truthful backend loop:

1. read the affected contract and endpoint surface first,
2. make the smallest clean change,
3. run the smallest repo-native gate that proves it,
4. update docs when runtime, mode support, or supportability truth changes,
5. move to the PR-grade gate when contracts, upstream behavior, or evidence posture are affected.

## Common Commands

- `make install`
- `make check`
- `make ci`
- `make test-unit`
- `make test-integration`
- `make test-e2e`
- `make mesh-contract-validate`
- `make openapi-gate`
- `make migration-smoke`
- `make migration-apply`
- `make image-supply-chain-gate`
- `make docker-build`

`make migration-smoke` and `make migration-apply` both validate the governed no-schema migration
contract. `lotus-risk` currently has no persistent DPM schema or Postgres migration to apply.

`make docker-build` passes Git commit SHA, branch/ref, service version, build timestamp, repository
URL, image digest field, and CI pipeline/run ID into OCI labels and runtime environment metadata
exposed by `/metadata` and `/version`.

`make image-supply-chain-gate` protects the release contract: CI-only image push, Git-SHA image
tags, OCI labels, SBOM, vulnerability scan, image signing, provenance attestation, release-manifest
digest capture, Kubernetes digest deployment, same-digest promotion, and no secret-like Docker
`ARG` or `ENV` names.

## When to Use Which Gate

Use `make check` for:

1. focused contract and router changes,
2. engine-level implementation work,
3. documentation changes that mention commands or support posture,
4. mode-support or endpoint-shape changes that do not yet need the full PR-grade pass.

Use `make ci` when the change affects:

1. OpenAPI or vocabulary posture,
2. upstream integration behavior,
3. risk-product-surface alignment,
4. test-pyramid distribution,
5. Docker/runtime parity expectations,
6. image release evidence, metadata, or deployment manifest posture.

## Code-First Reading Order

For product and integration work, start from:

1. `src/app/app_factory.py`
2. `src/app/routers/`
3. `src/app/contracts/`
4. `src/app/services/`
5. `src/app/integrations/`

Then confirm with:

1. `docs/domain-apis/endpoint-matrix.md`
2. `docs/domain-apis/risk-product-surface-alignment.md`
3. `docs/index.md`
4. `docs/operations/development-workflow-and-ci-strategy.md`

## Docs-With-Code Rule

Update docs in the same slice when:

1. endpoint support changes,
2. mode support changes,
3. upstream dependency posture changes,
4. supportability claims change,
5. local runtime commands change,
6. downstream product-surface requirements change.

## Read Next

1. use [Validation and CI](./Validation-and-CI.md) for the gate details,
2. use [RFC Index](./RFC-Index.md) when work maps to a local RFC family,
3. use [Integrations](./Integrations.md) when downstream contract semantics are involved.
