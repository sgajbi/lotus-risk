# Repository Engineering Context

This file provides repository-local engineering context for `lotus-risk`.

For platform-wide truth, read:

1. `../lotus-platform/context/LOTUS-QUICKSTART-CONTEXT.md`
2. `../lotus-platform/context/LOTUS-ENGINEERING-CONTEXT.md`
3. `../lotus-platform/context/CONTEXT-REFERENCE-MAP.md`

## Repository Role

`lotus-risk` is the authoritative risk analytics service in Lotus.

It owns drawdown, rolling risk, attribution, concentration, and related risk review analytics.

## Business And Domain Responsibility

This repository owns:

1. risk analytics calculations,
2. risk workspace supportability and decomposition payloads,
3. drawdown and concentration review data,
4. governed regime scenario-pack evaluation for downstream construction and stress posture,
5. integration-ready risk contracts consumed by `lotus-gateway` and domain consumers such as
   `lotus-manage`.

## Current-State Summary

Current repository posture:

1. `lotus-risk` is the domain authority for risk analytics in the ecosystem,
2. the service supports the current Workbench risk workspace through gateway-backed contracts,
3. the CI contract is explicit and strong, with no-alias, vocabulary, OpenAPI, test-pyramid, security, coverage, and Docker enforcement,
4. RFC-0008 establishes the current enterprise-readiness baseline: supported risk analytics are credible for the canonical private-banking portfolio, while unrestricted enterprise-bank approval still requires downstream proof and broader seeded portfolio archetype coverage,
5. current work often involves balancing analytical correctness, contract quality, and front-office usability,
6. upstream use of `lotus-core` and `lotus-performance` is now documented under the RFC-0082 upstream contract-family map,
7. repo-native RFC-0086 product and consumer declarations now live under `contracts/domain-data-products/` with a local `make domain-data-product-gate` validation path,
8. RFC-0087 trust telemetry proof for `RiskMetricsReport` now lives under
   `contracts/trust-telemetry/` and is validated by `tests/unit/test_trust_telemetry.py` against
   the platform trust telemetry validator when `lotus-platform` is available,
9. `RegimeScenarioPackEvaluation:v1` is a repo-native domain data product exposed through
   `POST /analytics/risk/regime-scenario-pack/evaluate`; it evaluates caller-supplied exposure
   weights against governed CIO scenario-pack definitions and returns source-owned worst-case loss,
   threshold breach posture, lineage, supportability, and bounded reason codes.
10. `RollingRiskMetricsReport:v1` now has implementation-backed methodology truth for
    `ROLLING_TRACKING_ERROR`: the docs and tests pin inner date alignment, percentage-point to
    decimal conversion, `ddof=1` sample standard deviation, annualized decimal-ratio output,
    warm-up/null behavior, and no-aligned-benchmark supportability posture.

## Architecture And Module Map

Primary areas:

1. `src/`
   risk application and analytics implementation.
2. `contracts/`
   repo-native domain product declarations, trust telemetry fixtures, and related machine-readable
   contract files.
3. `scripts/`
   OpenAPI, vocabulary, dependency-health, and test-pyramid governance.
4. `docs/standards/`
   local standards and contract guidance.
5. `tests/`
   unit, integration, and e2e validation.
6. `wiki/`
   canonical local source pages for repository wiki and onboarding navigation.

## Runtime And Integration Boundaries

Runtime model:

1. FastAPI-backed risk analytics service,
2. primarily consumed through `lotus-gateway`,
3. integrates with `lotus-core` and `lotus-performance` for stateful or cross-analytic flows where required.

Boundary rules:

1. risk analytics authority stays here,
2. gateway and UI should not duplicate risk logic or narrative improperly,
3. monetary-float governance applies only where money-bearing identifiers require it, not generic analytics terms,
4. supportability and evidence posture should remain truthful and data-backed,
5. downstream consumers must preserve signed VaR semantics, attribution reconciliation fields, issuer active-risk gating, concentration-only simulation support, and audit lineage metadata as documented in `docs/domain-apis/risk-product-surface-alignment.md`,
6. `lotus-core` must be consumed as a governed source-data, analytics-input, snapshot/simulation, and support-metadata authority, while `lotus-performance` remains the authority for performance return and benchmark exposure context inputs.
7. RFC-0108 calculation supportability is source-owned in this repository across `risk/calculate`,
   drawdown, rolling metrics, historical attribution, and concentration through
   `metadata.calculation_supportability` plus bounded
   `lotus_risk_calculation_supportability_total` labels. The supportability contract publishes
   explicit `metric_labels`, and tests prove the Prometheus labels remain bounded to `operation`,
   `supportability_state`, `reason`, and `freshness_bucket` without portfolio, client,
   correlation, trace, security, request-body, or response-body label fields.

Canonical direct local validation ports:

1. `lotus-risk`: `http://localhost:8130`
2. `lotus-performance`: `http://localhost:8002`
3. `lotus-core` query APIs: `http://localhost:8202`

## Repo-Native Commands

Use these commands as the primary local contract:

1. install
   `make install`
2. fast local gate
   `make check`
3. PR-grade local gate
   `make ci`
4. run unit tests
   `make test-unit`
5. run integration tests
   `make test-integration`
6. run e2e tests
   `make test-e2e`
7. validate repo-native domain product declarations
   `make domain-data-product-gate`

## Validation And CI Expectations

`lotus-risk` uses explicit CI lanes:

1. `Remote Feature Lane`
2. `Pull Request Merge Gate`
3. `Main Releasability Gate`

Important validation expectations:

1. no-alias, OpenAPI, vocabulary, and test-pyramid gates are active,
2. security audit and migration smoke are required,
3. split test suites plus coverage and Docker build are part of the merge gate,
4. risk correctness and evidence posture must remain aligned with the product and gateway contract.
5. repo-native domain product declarations must stay aligned with RFC-0084 trust registries and any transitional platform mirrors until aggregation fully federates.

## Standards And RFCs That Govern This Repository

Most relevant current governance:

1. `../lotus-platform/rfcs/RFC-0065-lotus-performance-to-lotus-performance-and-lotus-risk-split.md`
2. `../lotus-platform/rfcs/RFC-0067-centralized-api-vocabulary-inventory-and-openapi-documentation-governance.md`
3. `../lotus-platform/rfcs/RFC-0072-platform-wide-multi-lane-ci-validation-and-release-governance.md`
4. `../lotus-platform/rfcs/RFC-0073-lotus-ecosystem-engineering-context-and-agent-guidance-system.md`
5. `../lotus-platform/rfcs/RFC-0082-lotus-core-domain-authority-and-analytics-serving-boundary-hardening.md`
6. `docs/domain-apis/RFC-0082-upstream-contract-family-map.md`
7. `docs/rfcs/RFC-0008-enterprise-bank-readiness-and-live-risk-validation-baseline.md`
8. `docs/standards/`

## Known Constraints And Implementation Notes

1. this repo sits close to front-office-facing risk workflows, so analytical contract drift is visible quickly in the UI,
2. over-broad governance rules can damage analytics work if they are not scoped carefully,
3. risk evidence and supportability posture must remain data-backed, not decorative or speculative,
4. when risk review flows change in Workbench or Gateway, this repo’s context should be checked for alignment,
5. live validation defaults to `PB_SG_GLOBAL_BAL_001`; do not claim broader enterprise portfolio-archetype coverage until `docs/operations/live-risk-validation-matrix.md` has real seeded portfolio IDs and evidence,
6. stateful historical attribution `ACTIVE_RISK + ISSUER` is intentionally gated until benchmark issuer exposure semantics are approved,
7. transport optimization across upstream services should start with contract and retrieval-shape evidence before any gRPC proposal,
8. `wiki/` inside the repository is the authored documentation source if a GitHub wiki is published later,
9. RFC-0087 preparation should reuse repo-owned readiness, observability, and lineage signals before introducing any new trust publication surface.

## Context Maintenance Rule

Update this document when:

1. major risk modules or payload families change,
2. repo-native commands or CI lane expectations change,
3. upstream integration posture changes materially,
4. supportability, evidence, or decomposition model assumptions change,
5. current product-facing usage or rollout posture changes,
6. RFC-0082 upstream contract-family classification or consumer conformance posture changes,
7. wiki ownership or publication workflow changes,
8. repo-native declaration locations, validation commands, or transitional mirror posture change.

## Cross-Links

1. `../lotus-platform/context/LOTUS-QUICKSTART-CONTEXT.md`
2. `../lotus-platform/context/LOTUS-ENGINEERING-CONTEXT.md`
3. `../lotus-platform/context/CONTEXT-REFERENCE-MAP.md`
4. `../lotus-platform/context/Repository-Engineering-Context-Contract.md`
5. [Lotus Developer Onboarding](../lotus-platform/docs/onboarding/LOTUS-DEVELOPER-ONBOARDING.md)
6. [Lotus Agent Ramp-Up](../lotus-platform/docs/onboarding/LOTUS-AGENT-RAMP-UP.md)
