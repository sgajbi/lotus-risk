# Validation and CI

## Quality Signal Map

Current posture: `lotus-risk` uses repo-native Make targets in local validation and GitHub lanes so
agents and engineers can reproduce the same evidence before opening or merging a PR.

| Signal | Repo-native command | Protected evidence |
| --- | --- | --- |
| Fast local contract | `make check` | lint, typecheck, API, mesh, image supply-chain, source-size, and unit proof |
| PR-grade local contract | `make ci` | architecture, dependency, migration, coverage, security, Docker, and release posture |
| Image release contract | `make image-supply-chain-gate` | CI-only push, SBOM, vulnerability scan, signing, provenance, manifest, and digest deployment |

## Lane Model

`lotus-risk` follows the Lotus CI lane model:

1. `Remote Feature Lane`
2. `Pull Request Merge Gate`
3. `Main Releasability Gate`

`Main Releasability Gate` does not run on push. It is dispatched by
`merged-pr-main-releasability.yml` once a pull request merges, against an immutable tag created at
the merge commit, and its first job refuses to continue unless the checked-out revision matches the
`expected_sha` it was dispatched with.

That is deliberate. Automated merges run under `secrets.LOTUS_AUTOMERGE_TOKEN`; under
`github.token` GitHub would not treat the merge push as a trigger and the gate would silently not
run. A dispatcher that fails is visible; a suppressed push trigger is not. Gate concurrency is also
keyed per commit rather than per branch, so a later merge cannot cancel an earlier commit's
in-flight gate.

The immutable dispatch tag is consumed infrastructure, not a release. An `always()` cleanup job
runs after the independent workflow-lint branch and the full Docker-gate dependency chain reach a
terminal state. It deletes only `main-releasability-<expected_sha>` after verifying the ref points
to that exact SHA. Lookup/deletion failures warn without changing the analytical gate verdict, and
an already-absent ref is harmless. Because the tag is reclaimed even after a failed gate, an
operator who needs a later rerun must recreate `main-releasability-<sha>` at the exact commit and
dispatch `main-releasability.yml` with the same `expected_sha`; the run reclaims it again.

**Auditing a merge:** use `gh run list --commit <full-sha>`. Listing by `--branch main` misses the
run, because the dispatch ref is a tag rather than `main`.

The repo-native commands are designed to map to those lanes directly.

`Action Reference Resolution` is a separate daily and manually dispatchable network check. It
enumerates every external `uses:` reference and asks the GitHub API whether its repository and
pinned tag or commit still exist. A missing reference in an accessible repository or an empty
inventory fails; an inaccessible repository, API outage, or rate limit cancels the run so it is
visibly inconclusive rather than falsely green. Its evidence records the immutable commit SHA
behind each tag and includes actions selected through repository subpaths.
This complements the offline form check in `make github-actions-runtime-gate`, which remains fast
and deterministic for local and protected lanes.

## Primary Commands

- `make check` - fast local gate
- `make ci` - PR-grade local gate
- `make lint` - Ruff `0.16.4` check and format enforcement. The package pin and pre-commit hook use
  the same release; all findings from the upgrade are fixed or narrowly dispositioned. The only
  exceptions are exact-file rules for a governed Decimal signature and adversarial repository-path
  fixtures; there is no global ignore
- `make ci-local` - split-suite coverage loop without Docker
- `make ci-local-docker` - isolated Docker lane for the split-suite coverage loop; the image
  normalizes Python source modes so Ruff sees Git-equivalent permissions from Windows hosts
- `make quality-baseline` - report-only enterprise refactor baseline and quality scorecard
- `make mesh-contract-validate` - domain product, trust telemetry, and observability contract validation
- `make image-supply-chain-gate` - image metadata, CI-only push, digest deployment, SBOM, vulnerability scan, signing, provenance, and secret-free Docker metadata validation
- `make domain-data-product-gate` - blocking repo-native domain product declaration validation;
  invoked directly by both `check` and `ci` in addition to the shared mesh-contract dependency.
- `make idea-opportunity-evidence-gate` - blocking contract tests for the governed idea-opportunity
  risk evidence generator; invoked directly by both `check` and `ci`.
- `make openapi-gate` - generated schema quality
- `make openapi-artifact-gate` - generated artifact policy
- `make api-vocabulary-gate` - API vocabulary inventory validation
- `make no-alias-gate` - rejects Pydantic field aliases and `by_alias` serialisation under `src/`,
  so the wire contract is the field name and there is no second spelling of a payload
- `make architecture-gate` - import-linter contracts from `.importlinter`, including that the domain
  and service layers stay framework independent and never import FastAPI
- `make github-actions-runtime-gate` - workflow action runtime posture, and reference forms that
  cannot resolve syntactically. This runs *first* in both `check` and `ci`. It was added after
  `aquasecurity/trivy-action@0.32.0` - a tag that does not exist - sat in `image-release.yml` and
  broke the release supply chain before any step ran; see issue #227. The daily online resolver
  catches a well-formed tag such as `v9.99.0` that does not actually exist; see issue #231
- `make source-size-gate` - fails when any module grows past the governed line count or when the
  source scan inspects zero files; successful output names the inspected file count
- `make complexity-gate` - **blocking** cyclomatic complexity ratchet. Fails when the maximum rises
  above `24`, when rank D-F blocks exceed `1`, or when rank C blocks exceed `6`. All three are
  banked at the measured tree with no headroom, so an improvement left unbanked fails too. It was
  two `radon` report commands until issue #225 - neither accepts a failure threshold, so the target
  sat in the blocking lane and could not fail
- `make maintainability-report` - `radon mi` output. A report, not a gate, and deliberately no
  longer named as one
- `make dead-code-gate` - vulture findings at 80% confidence
- `make dependency-hygiene-gate` - deptry findings
- `make test-pyramid-gate` - the *product* test shape. Tests marked `pytest.mark.governance` assert
  about the repository rather than product behaviour and are deselected, because counting them
  distorted the shape and made the gate hostile to adding CI-contract coverage; see issue #220
- `make test-unit` - unit suite
- `make test-integration` - integration suite
- `make test-e2e` - e2e suite
- `make migration-smoke` - CI migration smoke proof for the active no-schema contract
- `make migration-apply` - governed no-schema migration contract validation; this service has no
  persistent DPM schema to apply
- `make docker-build` - Docker build validation

## What `make check` Protects

`make check` currently covers:

1. lint,
2. no-alias governance,
3. typecheck,
4. OpenAPI quality,
5. API vocabulary validation,
6. mesh contract validation,
7. image supply-chain validation,
8. source-size regression protection,
9. unit-focused default test execution.

## What `make ci` Adds

`make ci` is the local PR-grade gate. It adds:

1. no-schema migration contract smoke,
2. test-pyramid validation,
3. security audit,
4. split unit, integration, and e2e suites,
5. coverage enforcement,
6. image supply-chain validation,
7. Docker build validation.

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
5. configured-only dependency readiness posture plus endpoint-level upstream failure posture,
6. release images that are tagged by Git SHA, labeled, scanned, signed, attested, accompanied by
   SBOM and release-manifest evidence, and deployed by digest.

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
