# Summary

- Refactors `lotus-risk` into a more modular, testable, observable, and governable backend while
  preserving existing risk analytics behavior.
- Splits the former monolithic FastAPI entry point, large service engines, downstream clients,
  OpenAPI examples, and risk/concentration/rolling/drawdown/attribution helpers into focused
  modules.
- Promotes quality, OpenAPI, architecture, security, source-size, observability, and evidence
  checks into repeatable local and GitHub gates.

# Why

This PR follows `docs/architecture/ENTERPRISE_BACKEND_REFACTORING_INSTRUCTIONS.md`. The goal is not
cosmetic cleanup; it is to make `lotus-risk` easier to understand, safer to change, easier to test,
easier to operate, and credible for enterprise bank review.

# Scope

- [x] Single enterprise backend refactor branch with small non-squash commits.
- [x] No unrelated product behavior changes intentionally mixed in.
- [x] Baseline quality/reporting foundation created before major refactoring.
- [x] Before/after scorecard maintained in `quality/quality_scorecard.md`.

# Issue Closure

Closes #159.
Fixes #157.
Fixes #158.
Fixes #160.
Fixes #161.
Fixes #162.
Fixes #163.
Fixes #164.
Fixes #165.
Fixes #166.
Fixes #167.
Fixes #168.
Fixes #169.
Fixes #170.
Fixes #171.
Fixes #172.
Fixes #173.
Fixes #174.
Fixes #175.
Fixes #176.
Fixes #177.
Fixes #178.
Fixes #179.
Fixes #180.
Fixes #181.
Fixes #182.
Fixes #183.
Fixes #184.
Fixes #185.
Fixes #186.
Fixes #187.
Fixes #188.
Fixes #189.
Fixes #190.
Fixes #191.
Fixes #193.
Fixes #195.

# Refactoring Approach

1. Establish baseline quality, scorecard, CI measurement, and review ledger.
2. Extract FastAPI app construction into `src/app/app_factory.py` while keeping `src/app/main.py`
   as a stable ASGI export.
3. Move routers, middleware, downstream dependency resolution, API error examples, and request
   examples into focused modules.
4. Decompose large risk, concentration, rolling, drawdown, attribution, scenario, and downstream
   client modules in behavior-preserving slices with focused tests.
5. Promote OpenAPI, architecture, source-size, security, observability, and quality evidence into
   gates and durable documentation.

# Before/After Scorecard

Authoritative scorecard: `quality/quality_scorecard.md`.

Measured highlights:

- `src/app/main.py`: `980` lines and `22` route/middleware/handler decorators before; `10` lines
  and `0` decorators now.
- Largest behavior units: `calculate_risk` was `284` lines, `calculate_rolling_metrics` was `230`
  lines, and `LotusPerformanceClient` was `256` lines; largest remaining function is
  `_issuer_concentration` at `37` lines and `LotusPerformanceClient` is `52` lines.
- Latest `make check` records `658` unit tests across `112` Python test files; the authoritative
  current scorecard is `quality/quality_scorecard.md`.
- Current baseline reports no C-or-worse cyclomatic-complexity candidates.
- Source-size gate enforces the current `450` line ceiling.

# Architecture Improvements

- `src/app/app_factory.py` owns FastAPI construction, middleware, exception handlers, and router
  registration.
- Routers live under `src/app/routers/`; downstream client resolution lives under
  `src/app/dependencies/`.
- Downstream HTTP profile, base URL, timeout, request execution, async polling, and payload parsing
  behavior is split from public client facades.
- Import-linter architecture contracts are recorded in `.importlinter` and exercised by
  `make architecture-gate`.

# API And OpenAPI Improvements

- Operation IDs, tags, summaries, descriptions, request examples, standard error examples, and
  duplicate operation ID checks are governed by `make openapi-gate`.
- `make openapi-artifact-gate` exports `output/openapi/lotus-risk.openapi.json` and generated
  evidence manifests under `output/openapi/`.
- OpenAPI artifact evidence contract is recorded in `quality/openapi_artifact_evidence.md`; exact
  branch, commit, timestamp, checksum, size, path count, operation count, repository URL, and CI run
  identity come from `output/openapi/lotus-risk.openapi.evidence.json`.

# Testing Improvements

- Unit coverage now protects app factory wiring, router extraction, downstream boundaries, OpenAPI
  governance, enterprise readiness, error mapping, observability contracts, and core analytics
  behavior.
- Local `make check` passed with `658` unit tests.
- PR merge gate runs unit, integration, and e2e suites with combined coverage enforcement.

# Security Improvements

- Authorization, service identity, capability checks, redaction, upstream error mapping,
  threat-model evidence, and deployment policy are documented and tested.
- `make security-audit` passed with `Known vulnerabilities: 0`.
- Remaining platform integration item: gateway-backed token-validation evidence when platform
  identity contracts are available.

# Observability Improvements

- `contracts/observability/lotus-risk-monitoring.v1.json` records dashboard panels and alert
  definitions.
- `make observability-contract-validate` validates monitoring contract structure and runbook
  anchors.
- `docs/runbooks/service-operations.md` records operator response guidance.

# Documentation Improvements

- Updated implementation-backed architecture, API governance, security, threat model, deployment
  policy, observability, operations, supported-features, wiki source, quality, and review-ledger
  documentation.
- `quality/agent_effectiveness_review.md` records recurring review of whether skills, guidance,
  documentation, or agent context should improve future work.

# Dependency Changes And Justification

- No runtime dependency changes are introduced by the final readiness slice.
- CI and quality workflow changes add or enforce source-size, OpenAPI artifact, architecture,
  dependency hygiene, dead-code, complexity, and security checks using repository-native commands
  and existing project tooling.

# Behavior, Migration, And Configuration Notes

- No intentional external API behavior change is claimed.
- No database migration is required.
- Runtime configuration documentation was strengthened; final target-runtime configuration proof
  remains a release-promotion evidence item.

# Validation Evidence

Local evidence used during final readiness:

```text
python -m pytest tests\unit\test_final_pr_readiness_evidence.py -q
python -m ruff check tests\unit\test_final_pr_readiness_evidence.py
make security-audit
make check
```

Latest local results:

- `make check`: passed, including lint, format check, no-alias guard, typecheck, OpenAPI gate,
  OpenAPI artifact gate, API vocabulary gate, mesh contract validation, source-size gate, and
  `658` unit tests.
- `make security-audit`: passed with `Known vulnerabilities: 0`.
- Latest pushed branch checks before PR creation:
  - `Quality Baseline`: success.
  - `Remote Feature Lane`: success.

PR evidence after opening:

- Attach or reference `output/openapi/lotus-risk.openapi.json` using
  `output/openapi/lotus-risk.openapi.evidence.json` as the checksum manifest.

# Known Limitations

- Do not claim unrestricted enterprise portfolio-archetype coverage beyond seeded repository
  evidence.
- Gateway-backed token-validation proof remains a platform/gateway integration item.
- Production telemetry thresholds should be recalibrated after deployment.
- Some service and contract modules remain future maintainability targets.
- GitHub wiki publication remains a post-merge closure step for branch-authored wiki files.

# Follow-Up Backlog

- Publish repo-authored wiki source after merge using
  `..\lotus-platform\automation\Sync-RepoWikis.ps1 -Publish -Repository lotus-risk`.
- Add gateway-backed token-validation evidence when platform identity contracts are available.
- Capture final enterprise runtime configuration proof before release promotion.
- Continue behavior-preserving reduction of remaining service and contract hotspots.
- Recalibrate observability alert thresholds with production telemetry.

# Review Focus Areas

- Router/app factory decomposition and dependency direction.
- Downstream client lifecycle, timeout, error mapping, and pooling behavior.
- OpenAPI governance and artifact evidence.
- Security posture documentation and fail-closed enterprise readiness behavior.
- Test quality around extracted analytics helpers and operator-facing evidence.

# CI Expectations

- [x] Feature branch `Quality Baseline` is green.
- [x] Feature branch `Remote Feature Lane` is green.
- [x] `Pull Request Merge Gate` is green after PR creation.

# Post-Merge Hygiene

- [ ] Delete remote feature branch.
- [ ] Delete local feature branch.
- [ ] Sync local `main` with `origin/main`.
- [ ] Publish repo-authored wiki source to the GitHub wiki target.

# Post-Merge Closure

Historical post-merge closure evidence for PR #149 is recorded in
`quality/final_refactor_closure_audit.md`. Current post-merge closure evidence must be recorded for
the final PR after it is merged.
