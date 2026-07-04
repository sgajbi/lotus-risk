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
   optional reconciled per-security contribution rows, source-owned CIO approval, effective-period,
   and portfolio-applicability posture, threshold breach posture, lineage, supportability, and bounded
   reason codes; the v3 methodology truth now lives in
   `docs/methodologies/metrics/regime-scenario-pack-evaluation.md`.
10. `RiskEventAffectedCohort:v1` is a repo-native domain data product exposed through
    `POST /analytics/risk/risk-event-cohorts/evaluate`; it evaluates candidate portfolios and
    source-supplied exposure weights against governed risk-event definitions and returns affected
    membership, exclusions, impact scores, source refs, supportability, and bounded reason codes
    for future manage wave-trigger consumption without creating waves or campaign approvals.
11. `MandateRiskHealthContext:v1` is a repo-native domain data product exposed through
    `POST /analytics/risk/mandate-health-context`; it derives bounded mandate risk health posture
    from source-owned tracking-error methodology, returns threshold breach state, methodology
    posture, lineage fingerprints, and bounded reason codes for future `lotus-manage`
    consumption, and explicitly does not create mandate actions, rebalance waves, client
    communications, orders, or execution.
12. `RiskMetricsReport:v1` now has implementation-backed methodology truth for `VOLATILITY`,
    `DRAWDOWN`, `SHARPE`, `SORTINO`, `VAR`, `BETA`, `TRACKING_ERROR`, and
    `INFORMATION_RATIO`: the docs and tests pin
    percentage-point input conventions, optional
    log-return transformation, frequency compounding before metric calculation, drawdown
    cumulative-wealth/running-peak behavior, `ddof=1` sample
    standard deviation/covariance/variance behavior, decimal volatility, risk-free, Sortino, VaR,
    tracking-error, and information-ratio details,
    percentage-point-squared beta covariance/benchmark-variance details, annualized
    percentage-point `metrics.VOLATILITY.value`, signed percentage-point
    `metrics.DRAWDOWN.value`, dimensionless annualized
    `metrics.SHARPE.value`, dimensionless annualized `metrics.SORTINO.value`, signed
    percentage-point `metrics.VAR.value`, dimensionless slope `metrics.BETA.value`,
    annualized percentage-point `metrics.TRACKING_ERROR.value`,
    dimensionless annualized `metrics.INFORMATION_RATIO.value`, decimal tracking-error and
    information-ratio detail fields, decimal Sortino mean-return, MAR, excess-return,
    annualized-excess-return, and downside-deviation detail fields, signed VaR base, horizon, and
    expected-shortfall detail fields, default and override
    annualization-factor resolution where used, benchmark dependency posture for beta, tracking
    error, and information ratio, no benchmark dependency posture for Drawdown, Sharpe, Sortino,
    and VaR, no risk-free dependency posture for volatility, Drawdown, Sortino, VaR, beta,
    tracking error, and information ratio, no-annualization-factor posture for Drawdown, no-denominator posture for
    volatility and tracking error, zero-volatility
    fail-closed posture for Sharpe, no-downside-observation fail-closed posture for Sortino,
    signed VaR loss-threshold posture, square-root horizon scaling,
    zero-benchmark-variance fail-closed posture for beta, zero-tracking-error fail-closed posture
    for information ratio, constant-active-return zero tracking-error posture, and
    insufficient-data / insufficient-aligned-observation failure behavior.
13. `RollingRiskMetricsReport:v1` now has implementation-backed methodology truth for
    `ROLLING_VOLATILITY`, `ROLLING_SHARPE`, `ROLLING_BETA`, `ROLLING_TRACKING_ERROR`,
    `ROLLING_INFORMATION_RATIO`, and `ROLLING_MAX_DRAWDOWN`: the docs and tests pin
    percentage-point to decimal conversion, `ddof=1` sample standard deviation/covariance/variance
    behavior, annualization where used, rolling maximum drawdown cumulative-wealth/running-peak
    behavior, annualized decimal volatility output, annualized decimal tracking-error output,
    dimensionless Sharpe, beta, and information-ratio output, decimal drawdown-ratio output,
    warm-up/null behavior, source-owned risk-free/benchmark alignment posture, no-aligned
    dependency supportability posture, zero-excess-volatility Sharpe flagging,
    zero-benchmark-variance beta flagging, and zero-tracking-error information-ratio flagging.
14. `DrawdownAnalyticsReport:v1` now has implementation-backed methodology truth for
    `MAX_DRAWDOWN`, `AVERAGE_DRAWDOWN`, `ULCER_INDEX`, and `TIME_UNDER_WATER_DAYS`: the docs and
    tests pin percentage-point input conventions, decimal cumulative-wealth/running-peak drawdown
    behavior, decimal `summary.max_drawdown`, `summary.average_drawdown`, non-negative
    `summary.ulcer_index`, and observation-count `summary.time_under_water_days` outputs, episode
    peak/trough/recovery semantics, strictly-underwater average-drawdown inclusion, full-path
    squared drawdown inclusion for ulcer index, strictly-underwater observation counting for time
    under water, empty-period insufficient-data posture, never-underwater zero-drawdown posture,
    duration-unit day counter behavior, and episode-list filter isolation from the summary
    maximum, average, ulcer-index, and time-under-water drawdown values.
15. `ConcentrationRiskReport:v1` now has implementation-backed methodology truth for
    `POSITION_HHI`, `TOP_POSITION_WEIGHT`, `TOP_N_CUMULATIVE_WEIGHT`, `ISSUER_HHI`, and
    `TOP_ISSUER_WEIGHT`: the docs and tests pin
    stateless, stateful, and simulation source resolution, positive numeric position-value
    extraction, market-value versus quantity fallback precedence, decimal position-weight
    construction, conventional `0..10000` Herfindahl-Hirschman scaling for HHI, decimal `0..1`
    top-position and top-N cumulative weight output, six-decimal response rounding,
    proposed-state fallback to current values when projected values are unavailable, deterministic
    top-position driver selection, top-N cumulative summation, covered-subset issuer aggregation,
    legal versus ultimate-parent issuer grouping, issuer-enrichment precedence, issuer coverage
    and supportability posture, deterministic top-issuer driver selection, top-issuer
    proposed-state fallback, input-universe option boundaries, and issuer-enrichment isolation
    from `risk_proxy.hhi_*` and
    `single_position_concentration.top_position_*` / `top_n_cumulative_weight_*` outputs.
    `lotus-idea` is now an approved consumer for `ConcentrationRiskReport:v1` so it can preserve
    risk-owned concentration evidence in opportunity-intelligence workflows without taking over
    concentration methodology, mesh certification, client publication, or supported-feature
    authority.

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
4. FastAPI lifespan owns reusable, dependency-specific downstream HTTP connection pools and closes
   them after entering draining posture during shutdown.

Boundary rules:

1. risk analytics authority stays here,
2. gateway and UI should not duplicate risk logic or narrative improperly,
3. monetary-float governance applies only where money-bearing identifiers require it, not generic analytics terms,
4. supportability and evidence posture should remain truthful and data-backed,
5. downstream consumers must preserve signed VaR semantics, attribution reconciliation fields, issuer active-risk support metadata, concentration-only simulation support, and audit lineage metadata as documented in `docs/domain-apis/risk-product-surface-alignment.md`,
6. `lotus-core` must be consumed as a governed source-data, analytics-input, snapshot/simulation, and support-metadata authority, while `lotus-performance` remains the authority for performance return and benchmark exposure context inputs.
7. production ASGI runtimes must keep lifespan support enabled so downstream connection pooling and
   shutdown cleanup remain effective; explicitly injected clients are preserved for controlled
   runtimes and tests.
8. RFC-0108 calculation supportability is source-owned in this repository across `risk/calculate`,
   drawdown, rolling metrics, historical attribution, and concentration through
   `metadata.calculation_supportability` plus bounded
   `lotus_risk_calculation_supportability_total` labels. The supportability contract publishes
   explicit `metric_labels`, and tests prove the Prometheus labels remain bounded to `operation`,
   `supportability_state`, `reason`, and `freshness_bucket` without portfolio, client,
   correlation, trace, security, request-body, or response-body label fields. Historical
   attribution now degrades response-level calculation supportability whenever any source-owned
   attribution set emits quality flags, so downstream consumers do not treat missing grouping data,
   empty active-risk alignment, or unsupported attribution combinations as fully ready analytics.
9. downstream base URLs are validated at adapter construction and must be valid HTTP(S) service
   endpoints without embedded credentials, query strings, fragments, whitespace, or control
   characters; runtime-owned settings are documented in `docs/configuration.md`.
10. `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true` is fail-closed bank mode: application construction
    requires authorization plus explicit policy, key, rotation, capability, payload-limit, and
    upstream URL configuration.
11. API errors preserve the standard Lotus `error` envelope while adding RFC 7807/problem-details
    compatibility fields inside the same object; do not replace this with a breaking top-level
    problem-details shape without a versioned migration.
12. Upstream adapter exceptions must keep raw dependency text out of public `message` and
    problem-details `detail` fields. Preserve diagnosis through structured `details` fields:
    `service`, `operation`, `category`, `retryable`, and `upstream_status_code` where available.
13. Operation-specific upstream HTTP states must be modeled at the shared downstream executor
    boundary with explicit accepted statuses, not by bypassing common error normalization. The
    lotus-performance async returns result endpoint treats `202` and `404` as pending; unexpected
    result `4xx`/`5xx` statuses still use standard upstream classification.
14. Shared stateful return parsing owns malformed upstream return-date classification for
    risk/calculate, drawdown, rolling, and attribution consumers; malformed string dates are
    dependency contract failures (`UPSTREAM_INVALID_RESPONSE`), while non-string dates remain
    ignored as unusable rows.
15. GitHub mesh-contract validation requires `lotus-platform` contract truth. Workflows provide it
    as `.lotus-platform`; local runs can use either a sibling `../lotus-platform` checkout or
    `LOTUS_PLATFORM_ROOT`.
16. Enterprise authorization route truth lives in `enterprise_authorization.SUPPORTED_WRITE_ROUTES`.
    Startup capability-rule coverage, request-time capability matching, generated OpenAPI
    caller-context extensions, and OpenAPI quality gates must remain aligned to that inventory.
17. Enterprise downstream runtime-control validation lives in
    `integrations.downstream_profile_env.invalid_downstream_runtime_setting_issues`. Local
    development may fall back to defaults for invalid timeout, pool, keepalive, and async polling
    overrides, but enterprise runtime enforcement must reject explicit invalid overrides with
    bounded `invalid_downstream_runtime_setting:<ENV_NAME>` issue codes.
18. Enterprise body-limit proof must remain executable, not narrative. `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES`
    is the in-process write payload guard; `ENTERPRISE_INGRESS_MAX_BODY_BYTES` and
    `ENTERPRISE_ASGI_MAX_BODY_BYTES` prove external ingress/proxy and ASGI/server limits are present
    and no larger than the app limit. Direct local Uvicorn/Compose is local-only for this posture.
19. Enterprise trusted-ingress proof lives in `enterprise_trusted_ingress.py`. Bank-mode startup
    requires `ENTERPRISE_TRUSTED_INGRESS_SECRET`; write requests and protected operator endpoints
    (`/ops`, `/ops/trust-telemetry`, and `/metrics`) must reject missing or invalid
    `X-Lotus-Trusted-Ingress` before trusting propagated actor, service identity, or capability
    headers. Health and readiness probes remain platform-compatible.
20. Runtime downstream composition lives under `src/app/runtime`. Lifespan creates concrete
    `lotus-core` and `lotus-performance` clients with reusable HTTP pools; routers receive the
    typed `RuntimeDownstreamClients` dependency and resolve stateful ports from that boundary only.
    Request-time code must fail closed with `RUNTIME_COMPOSITION_ERROR` when required runtime state
    is missing; do not reintroduce concrete client construction, class monkeypatch fallbacks, or
    service-locator helpers under router/dependency modules.
21. Keep runtime posture modern and current: retained local compatibility or direct-run behavior
    must be explicitly scoped to local development and must not become a bank-readiness, production,
    or enterprise claim without machine-readable proof and tests. Do not add new legacy aliases,
    local-only shortcuts, or stale compatibility surfaces while fixing issue slices.
22. `/health/ready`, `/ops`, and `/ops/trust-telemetry` publish configured-only dependency posture
    by default. Dependency rows with `status="configured"` and
    `detail="configured_only_no_probe"` prove source-safe URL configuration, not live upstream
    reachability. Keep live dependency diagnosis on endpoint-level upstream errors, bounded
    supportability metadata, upstream metrics, or explicit runtime dependency-status overrides
    until an implementation-backed active probe or periodic updater is intentionally introduced
    with bounded timeouts, tests, and operator docs.

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
8. remove known local/generated artifacts
   `make clean`

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
6. `make ci` is the PR-grade local aggregate and includes architecture, mesh-contract,
   complexity, source-size, dependency-hygiene, dead-code, migration, test-pyramid, coverage,
   security, and Docker evidence; `ci-local` is only a split-suite coverage loop without Docker.

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
6. stateful historical attribution `ACTIVE_RISK + ISSUER` is supported through lotus-performance benchmark exposure context issuer groups introduced in lotus-performance PR #165,
7. transport optimization across upstream services should start with contract and retrieval-shape evidence before any gRPC proposal,
8. `wiki/` inside the repository is the authored documentation source for the published GitHub
   wiki; use `../lotus-platform/automation/Sync-RepoWikis.ps1 -CheckOnly -Repository lotus-risk`
   before merge and `../lotus-platform/automation/Sync-RepoWikis.ps1 -Publish -Repository
   lotus-risk` after merge when repo-local wiki truth changes,
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
