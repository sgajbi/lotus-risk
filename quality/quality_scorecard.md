# Lotus Risk Quality Scorecard

This scorecard tracks measurable movement from the enterprise refactor baseline
introduced in commit `3254774` to the current feature branch state. It is
evidence for PR readiness, not a completion claim.

| Dimension | Baseline evidence | Current evidence | Improvement shown | Remaining target |
| --- | --- | --- | --- | --- |
| API modularity | `src/app/main.py` had 22 route/middleware/handler decorators and 980 lines | `src/app/main.py` has 0 route/middleware/handler decorators and 10 lines | App construction, routers, middleware, errors, and downstream dependency resolution are split into modules | Keep router boundaries green and prevent app-entry-point regression |
| Code size | Largest files included `src/app/services/concentration_engine.py` at 981 lines and `src/app/main.py` at 980 lines | Largest source files are contract/service modules; no source file over 800 lines after the latest baseline | Monolithic API and concentration service files were split; contract example payloads were extracted | Continue reducing service hotspots over 600 lines |
| Largest behavior units | Largest function/class included `calculate_risk` at 284 lines, `calculate_rolling_metrics` at 230 lines, and `LotusPerformanceClient` at 256 lines | Largest remaining function is `_build_attribution_set` at 53 lines; `LotusPerformanceClient` is 113 lines | Large engines and clients were decomposed into helpers, services, routers, and polling/parsing functions | Continue reducing engine-level orchestration hotspots |
| Complexity | Baseline reported C-or-worse candidates across large service, contract, and readiness code | Current baseline reports no C-or-worse candidates in the complexity snapshot | C-level candidates in concentration parsing, risk period resolution, rolling/attribution validation, and enterprise authorization were removed | Keep radon report-only evidence clean while thresholds are tightened |
| Architecture enforcement | Import-linter, architecture docs, and quality workflow were introduced as report-only baseline | `make architecture-gate` is green locally and in feature-lane CI | Architecture boundary checks are now part of routine slice validation | Extend contracts as service boundaries mature |
| OpenAPI governance | Operation IDs were not visibly standardized; route-level examples needed certification after router extraction | Operation IDs are explicit; JSON mutation request examples are modularized and enforced by `make openapi-gate` against the generated schema | OpenAPI metadata is easier to review, no longer buried in large contract classes, and now fails missing operation IDs/request examples in CI lanes | Standardize secondary Spectral lint artifact export before final PR |
| Tests | 77 Python test files at initial baseline; repo-native coverage gate existed | 87 Python test files; 436 tests collected in the latest baseline; OpenAPI gate logic has focused regression tests | Focused unit/integration coverage protects router, client, contract, middleware, service, and OpenAPI-governance refactors | Add more negative/security contract certification tests |
| Security | Enterprise audit middleware, redaction tests, and upstream error mapping existed; abuse-control evidence was still a gap | Authorization checks are decomposed and covered by enterprise-readiness tests; threat-model/abuse-control evidence is pinned in `docs/security-threat-model.md`; Bandit and pip-audit remain green in baseline | Security behavior and abuse controls are easier to inspect and test without changing enforcement semantics | Finalize deployment identity enforcement decisions before PR |
| Observability | HTTP, endpoint execution, supportability, freshness metrics, and correlation existed but needed consolidated docs | Observability docs exist and endpoint/upstream metrics remain covered by tests and baseline validation | Metrics/correlation posture is preserved through router and client decomposition | Add dashboard/alert evidence or governed no-dashboard decision |
| Documentation and PR evidence | Baseline/reporting foundation was introduced with architecture, security, observability, runbook, wiki, and quality docs | `baseline_report.md`, `refactor_health_report.md`, and this scorecard are updated with current measured movement | Refactor progress is now auditable from generated reports and branch history | Final PR must summarize commands, CI, risks, and follow-up backlog |

## Current Gate Snapshot

- Local feature-lane checks used across recent slices: focused pytest packs,
  `make typecheck`, `make lint`, `make architecture-gate`, targeted `radon cc`,
  and `make quality-baseline`.
- GitHub checks are pushed after each slice and reviewed asynchronously:
  `Quality Baseline` and `Remote Feature Lane`.
- The latest baseline keeps the progressive gate posture report-only where
  thresholds are not final; generated OpenAPI schema governance is actively
  enforced through `make openapi-gate`.
