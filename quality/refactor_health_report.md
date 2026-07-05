# Lotus Risk Refactor Health Report

## Current Slice

The branch has moved beyond report-only scaffolding into measured modularity,
contract-size, client-boundary, runtime lifecycle hardening, complexity reduction,
and generated OpenAPI schema certification. The current baseline shows no
C-or-worse complexity candidates, while GitHub feature-lane checks are being
used asynchronously after each pushed slice.

## Highest Priority Refactor Targets

| Rank | Target | Evidence | Next action |
| --- | --- | --- | --- |
| 1 | Service module size | Concentration, attribution, and rolling public adapters have been split from stateful, simulation, and exposure-resolution helpers; remaining source-size pressure is concentrated in contract modules | Continue extracting cohesive orchestration, response-building, and dependency-resolution helpers with characterization tests |
| 2 | Contract module size | Concentration, rolling, risk, drawdown, attribution, and scenario request/response contracts are split; concentration, rolling, and drawdown response models are further split into metric/detail and top-level response modules; remaining contract-size pressure is concentrated in risk and input modules | Split reusable metadata or nested contract fragments only where it improves reviewability and preserves OpenAPI output |
| 3 | OpenAPI and certification evidence | `make openapi-gate` evaluates the generated FastAPI schema; `make openapi-artifact-gate` exports `output/openapi/lotus-risk.openapi.json` and validates Spectral policy expectations; `quality/openapi_artifact_evidence.md` records current checksum evidence | Regenerate and attach the final current OpenAPI artifact evidence to the PR |
| 4 | Security and abuse-control evidence | Authorization, audit, redaction, Bandit, pip-audit, payload-size limits, capability checks, threat-model evidence, bank deployment policy, and image supply-chain release controls are covered | Add upstream identity-provider token-validation evidence and inspect the first mainline image-release evidence before external release promotion |
| 5 | Observability operations evidence | Metrics/correlation support, dashboard panels, alert definitions, and runbook anchors are governed by the observability monitoring contract | Keep alert thresholds aligned with production telemetry after deployment |

## Progressive Gate Posture

1. Baseline/report-only: implemented and refreshed per slice.
2. Fail only new regressions: partially active through lint, typecheck,
   architecture gate, monetary-float guard, OpenAPI gate, image supply-chain
   gate, focused tests, and GitHub feature lane checks.
3. Enforce agreed thresholds: partially complete; complexity and the 450-line
   source-size ceiling are actively gated, OpenAPI generation is actively gated,
   security deployment policy and image supply-chain policy are documented and
   tested, and observability operations evidence is governed, but production
   telemetry thresholds still need final policy.
4. Enterprise-readiness gates: not complete; final PR still needs healthy PR
   merge-gate CI plus current generated OpenAPI artifact and command evidence.
