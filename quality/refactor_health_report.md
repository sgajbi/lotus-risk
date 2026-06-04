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
| 3 | OpenAPI and certification evidence | `make openapi-gate` evaluates the generated FastAPI schema; `make openapi-artifact-gate` exports `output/openapi/lotus-risk.openapi.json` and validates Spectral policy expectations | Attach generated OpenAPI artifact evidence to final PR |
| 4 | Security and abuse-control evidence | Authorization, audit, redaction, Bandit, pip-audit, payload-size limits, capability checks, and threat-model evidence are covered | Finalize deployment identity enforcement and server-level body-limit decisions before PR readiness |
| 5 | Observability operations evidence | Metrics/correlation support, dashboard panels, alert definitions, and runbook anchors are governed by the observability monitoring contract | Keep alert thresholds aligned with production telemetry after deployment |

## Progressive Gate Posture

1. Baseline/report-only: implemented and refreshed per slice.
2. Fail only new regressions: partially active through lint, typecheck,
   architecture gate, monetary-float guard, OpenAPI gate, focused tests, and
   GitHub feature lane checks.
3. Enforce agreed thresholds: not complete; complexity is clean, OpenAPI
   generation is actively gated, and observability operations evidence is
   governed, but file-size, security deployment policy, and production
   telemetry thresholds still need final policy.
4. Enterprise-readiness gates: not complete; final PR still needs healthy CI,
   OpenAPI/security/observability certification evidence, risks, and follow-up
   backlog.
