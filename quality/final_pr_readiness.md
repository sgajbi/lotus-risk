# Lotus Risk Enterprise Refactor PR Readiness Pack

This pack is the draft evidence source for the final non-squash PR on
`feat/enterprise-risk-refactor-production-hardening`. It is not a completion claim. The PR should
only be opened after the branch is still clean, GitHub checks are healthy, and the generated
OpenAPI artifact is attached or referenced in PR evidence.

## Refactor Approach

The branch follows the enterprise backend refactoring playbook:

1. create baseline quality and CI measurement first,
2. split monolithic API entry-point behavior into app factory, routers, middleware, dependencies,
   and error metadata,
3. move downstream access behind dependency/provider boundaries,
4. reduce service and validation complexity in small behavior-preserving slices,
5. promote OpenAPI, architecture, security, observability, dependency, and quality checks from
   report-only evidence toward active gates,
6. keep implementation-backed docs, wiki source, and quality scorecards updated with the code.

## Before And After Scorecard

The authoritative before/after scorecard is `quality/quality_scorecard.md`.

Current measured highlights:

1. `src/app/main.py` moved from `980` lines and `22` route/middleware/handler decorators to `10`
   lines and `0` decorators.
2. The latest quality baseline reports no C-or-worse cyclomatic-complexity candidates.
3. The latest quality baseline collects `453` tests across `91` Python test files.
4. OpenAPI governance now enforces operation IDs, mutation request examples, duplicate operation ID
   checks, and generated artifact policy.
5. Security evidence now covers authorization headers, service identity, capability checks,
   redaction, dependency audit, threat-model evidence, and enterprise deployment security posture.
6. Observability evidence now covers metrics, dashboard panels, alert definitions, and runbook
   anchors.

## Architecture Improvements

Evidence:

1. `src/app/app_factory.py` owns FastAPI application construction.
2. `src/app/main.py` remains a stable ASGI export.
3. Routers live under `src/app/routers/`.
4. Downstream client resolution lives under `src/app/dependencies/`.
5. Import-linter contracts are recorded in `.importlinter` and exercised by `make architecture-gate`.

Remaining risk:

1. Several service and contract modules remain large enough to deserve later cohesive extraction:
   targeted rolling/concentration/drawdown/risk/attribution response fragments.

## API And OpenAPI Improvements

Evidence:

1. `make openapi-gate` validates generated FastAPI schema quality.
2. `make openapi-artifact-gate` exports `output/openapi/lotus-risk.openapi.json` and validates the
   artifact against repository Spectral policy expectations.
3. `tests/unit/test_openapi_quality_gate.py` and `tests/unit/test_openapi_artifact_gate.py` pin the
   gate behavior.
4. `quality/openapi_artifact_evidence.md` records the current generated artifact path, checksum,
   size, schema counts, and regeneration commands for PR attachment.

PR requirement:

1. Attach or reference the generated `output/openapi/lotus-risk.openapi.json` artifact in the final
   PR evidence, using `quality/openapi_artifact_evidence.md` as the checksum manifest.

## Testing Improvements

Evidence:

1. Focused tests protect app factory wiring, router extraction, downstream client boundaries,
   OpenAPI governance, security evidence, observability contracts, upstream error mapping,
   enterprise readiness, and risk analytics behavior.
2. The latest generated baseline records `453` collected tests and `97%` total coverage.
3. The final PR should list exact local commands and GitHub check names that passed.

## Security Improvements

Evidence:

1. `docs/security-threat-model.md` records current abuse cases and controls.
2. `docs/security-deployment-policy.md` records enterprise bank deployment mode.
3. `tests/unit/test_enterprise_readiness.py`, `tests/unit/test_security_evidence_docs.py`, and
   `tests/unit/test_enterprise_deployment_policy_docs.py` pin security posture.
4. `make security-audit` reports zero known vulnerabilities in the isolated project dependency
   audit.

Remaining risk:

1. Gateway-backed token-validation evidence must be added when platform identity contracts are
   available.
2. Final runtime configuration proof is still required before release promotion.

## Observability Improvements

Evidence:

1. `contracts/observability/lotus-risk-monitoring.v1.json` records dashboard panels and alert
   definitions.
2. `make observability-contract-validate` validates monitoring contract structure and runbook
   anchors.
3. `docs/runbooks/service-operations.md` records alert response steps.
4. `tests/unit/test_observability_operations_contract.py` pins operator evidence.

Remaining risk:

1. Alert thresholds should be recalibrated against production telemetry after deployment.

## Documentation Improvements

Evidence:

1. `docs/architecture.md`, `docs/api-governance.md`, `docs/security.md`,
   `docs/security-threat-model.md`, `docs/security-deployment-policy.md`, `docs/observability.md`,
   `docs/operations-runbook.md`, `docs/runbooks/service-operations.md`, and `docs/supported-features.md`
   record implementation-backed repository truth.
2. Repo-local wiki source has been updated for security and operations posture.
3. `quality/baseline_report.md`, `quality/refactor_health_report.md`, and
   `quality/quality_scorecard.md` provide generated measurable evidence.
4. `quality/openapi_artifact_evidence.md` records the generated OpenAPI artifact checksum and
   attachment metadata.

## Validation Evidence To Include In The PR

Use the final current outputs, not stale historical outputs:

```text
make lint
make typecheck
make architecture-gate
make openapi-gate
make openapi-artifact-gate
make observability-contract-validate
make security-audit
make quality-baseline
python -m pytest tests/unit/test_enterprise_readiness.py tests/unit/test_security_evidence_docs.py tests/unit/test_enterprise_deployment_policy_docs.py -q
```

GitHub evidence to cite:

1. `Quality Baseline`
2. `Remote Feature Lane`
3. `Pull Request Merge Gate` after the PR is opened
4. `Main Releasability Gate` only after merge/release promotion flow requires it

## Known Limitations

1. This branch should not claim unrestricted enterprise portfolio-archetype coverage beyond the
   seeded evidence available in the repository.
2. Runtime token-validation proof remains a platform/gateway integration evidence item.
3. Production telemetry threshold tuning remains post-deployment work.
4. Large service and contract modules remain future maintainability targets.

## Follow-Up Backlog

1. Attach generated OpenAPI artifact evidence to the final PR.
2. Add gateway-backed token-validation evidence when platform identity contracts are available.
3. Capture final enterprise runtime configuration proof before release promotion.
4. Continue reducing large service and contract modules in behavior-preserving slices.
5. Recalibrate observability alert thresholds with production telemetry.

## PR Assembly Checklist

Before opening the PR:

1. Ensure `git status --short --branch` is clean and tracking the pushed feature branch.
2. Confirm recent GitHub `Quality Baseline` and `Remote Feature Lane` checks are green.
3. Generate and preserve `output/openapi/lotus-risk.openapi.json` as PR evidence.
4. Copy the before/after summary from `quality/quality_scorecard.md`.
5. Include the known limitations and follow-up backlog from this file.

Do not merge until the PR merge gate is healthy and any required wiki publication steps are handled
according to the Lotus operating contract.
