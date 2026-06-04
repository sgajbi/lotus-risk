# Lotus Risk Refactor Health Report

## Current Slice

The branch has moved beyond report-only scaffolding into measured modularity,
contract-size, client-boundary, complexity reduction, and generated OpenAPI
schema certification. The current baseline shows no C-or-worse complexity
candidates, while GitHub feature-lane checks are being used asynchronously
after each pushed slice.

## Highest Priority Refactor Targets

| Rank | Target | Evidence | Next action |
| --- | --- | --- | --- |
| 1 | Service module size | Largest remaining source modules include `rolling_engine.py`, `concentration/resolvers.py`, `drawdown_engine.py`, and `attribution_engine.py` | Continue extracting cohesive orchestration, response-building, and dependency-resolution helpers with characterization tests |
| 2 | Contract module size | Contract modules are improved but `concentration.py`, `rolling.py`, `risk.py`, and `drawdown.py` remain prominent source files | Split reusable metadata or nested contract fragments only where it improves reviewability |
| 3 | OpenAPI and certification evidence | `make openapi-gate` now evaluates the generated FastAPI schema and fails missing operation IDs, duplicate operation IDs, missing endpoint docs/responses, missing JSON mutation examples, and missing schema field metadata | Standardize secondary Spectral artifact export/lint evidence before final PR readiness |
| 4 | Security and abuse-control evidence | Authorization, audit, redaction, Bandit, pip-audit, payload-size limits, capability checks, and threat-model evidence are covered | Finalize deployment identity enforcement and server-level body-limit decisions before PR readiness |
| 5 | Observability operations evidence | Metrics/correlation support and docs exist; dashboard/alert proof is still not final | Add alert/dashboard evidence or a governed no-dashboard decision with runbook linkage |

## Progressive Gate Posture

1. Baseline/report-only: implemented and refreshed per slice.
2. Fail only new regressions: partially active through lint, typecheck,
   architecture gate, monetary-float guard, OpenAPI gate, focused tests, and
   GitHub feature lane checks.
3. Enforce agreed thresholds: not complete; complexity is clean and OpenAPI
   generation is actively gated, but file-size, secondary Spectral lint,
   security, and observability thresholds still need final policy.
4. Enterprise-readiness gates: not complete; final PR still needs healthy CI,
   OpenAPI/security/observability certification evidence, risks, and follow-up
   backlog.
