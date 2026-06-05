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
| 1 | Service module size | Concentration, attribution, and rolling public adapters have been split from stateful, simulation, and exposure-resolution helpers; remaining source-size pressure is concentrated in contract modules | Continue extracting cohesive orchestration, response-building, and dependency-resolution helpers with characterization tests |
| 2 | Contract module size | Concentration request/response contracts are split; `rolling.py`, `risk.py`, and `drawdown.py` remain prominent source files | Split reusable metadata or nested contract fragments only where it improves reviewability and preserves OpenAPI output |
| 3 | OpenAPI and certification evidence | `make openapi-gate` evaluates the generated FastAPI schema; `make openapi-artifact-gate` exports `output/openapi/lotus-risk.openapi.json` and validates Spectral policy expectations; `quality/openapi_artifact_evidence.md` records current checksum evidence | Regenerate and attach the final current OpenAPI artifact evidence to the PR |
| 4 | Security and abuse-control evidence | Authorization, audit, redaction, Bandit, pip-audit, payload-size limits, capability checks, threat-model evidence, and bank deployment policy are covered | Add gateway-backed token-validation evidence and final runtime configuration proof before release promotion |
| 5 | Observability operations evidence | Metrics/correlation support, dashboard panels, alert definitions, and runbook anchors are governed by the observability monitoring contract | Keep alert thresholds aligned with production telemetry after deployment |

## Progressive Gate Posture

1. Baseline/report-only: implemented and refreshed per slice.
2. Fail only new regressions: partially active through lint, typecheck,
   architecture gate, monetary-float guard, OpenAPI gate, focused tests, and
   GitHub feature lane checks.
3. Enforce agreed thresholds: not complete; complexity is clean, OpenAPI
   generation is actively gated, security deployment policy is documented and
   tested, and observability operations evidence is governed, but file-size
   and production telemetry thresholds still need final policy.
4. Enterprise-readiness gates: not complete; final PR still needs healthy PR
   merge-gate CI plus current generated OpenAPI artifact and command evidence.
