# RFC-0008: Enterprise Bank Readiness and Live Risk Validation Baseline

- Status: Proposed
- Date: 2026-04-13
- Owners: lotus-risk
- Requires Approval From: lotus-risk maintainers, lotus-platform maintainers
- Depends On: lotus-core, lotus-performance, lotus-gateway, lotus-platform
- Related Standards: lotus-platform RFC-0067, RFC-0071, RFC-0072, lotus-risk RFC-0003, RFC-0004, RFC-0005, RFC-0006, RFC-0007

## Summary

`lotus-risk` has moved from prototype-shaped risk analytics toward a credible private-banking risk domain service.

Recent validation and implementation work established that the service can support the canonical private-banking portfolio `PB_SG_GLOBAL_BAL_001` across the major risk analytics surfaces:

1. volatility,
2. Sharpe,
3. Sortino,
4. drawdown,
5. beta,
6. tracking error,
7. information ratio,
8. value at risk,
9. concentration,
10. historical risk attribution,
11. rolling risk.

This RFC records the enterprise-readiness posture that follows from that work. It separates:

1. what is now implemented and live-validated,
2. what is intentionally unsupported and must remain explicit,
3. what remains before `lotus-risk` should be called enterprise-bank production-ready.

The conclusion is deliberately conservative:

1. `lotus-risk` is credible for controlled private-banking advisory and Workbench risk workflows,
2. `lotus-risk` is not yet fully enterprise-bank approved for unrestricted production use,
3. the remaining work is primarily operational resilience, audit lineage, observability, multi-portfolio validation, and final cross-service governance.

## Why This RFC Exists

The recent `lotus-risk` validation pass proved important analytical and contract behavior with live data. It also exposed the right next boundary.

The service is no longer mainly blocked by missing basic risk calculations. The core calculations are implemented and the canonical live portfolio has been reconciled endpoint by endpoint.

The remaining question is different:

1. can the service support enterprise-like banks,
2. can it do so under realistic dependency, audit, model-governance, and operational expectations,
3. can downstream product surfaces explain the results without misleading private-banking users,
4. can the service survive misconfiguration, partial upstream failure, and wider portfolio archetypes.

Without this RFC, there is a risk that the team over-reads successful live calculation validation as full enterprise production readiness.

This RFC makes the distinction explicit.

## Problem Statement

`lotus-risk` now has strong evidence that core risk analytics work for the canonical seeded private-banking portfolio. However, enterprise-bank support requires more than successful happy-path analytics.

The remaining risk areas are:

1. upstream dependency resilience is not yet proven under failure and degradation scenarios,
2. canonical URL and environment routing can still be misconfigured too easily,
3. issuer active-risk attribution remains intentionally unsupported because benchmark issuer exposure semantics are not available,
4. historical attribution residuals require careful user-facing explanation,
5. live validation is still narrow compared with a bank's portfolio universe,
6. audit lineage and model-validation evidence need stronger end-to-end consistency,
7. production observability still needs explicit proof across all endpoints and dependencies.

The service is therefore in a strong internal-pilot or near-production posture, not a final enterprise sign-off posture.

## Goals

1. Record the current live-validated `lotus-risk` analytics baseline.
2. Define what `enterprise-bank-ready` means for `lotus-risk`.
3. Preserve the trading-day calculation correction as a non-negotiable methodology requirement.
4. Document the intentional `ACTIVE_RISK + ISSUER` limitation clearly and keep it out of accidental future scope.
5. Define the remaining hardening and validation slices required before final enterprise sign-off.
6. Ensure downstream teams understand what can be safely used today and what requires additional governance.
7. Align analytics, API contracts, observability, and documentation with private-banking expectations.

## Non-Goals

1. This RFC does not introduce new risk metric families.
2. This RFC does not require changes in `lotus-core` or `lotus-performance` for the current slice.
3. This RFC does not turn `lotus-risk` into a market-data, benchmark-composition, or portfolio-construction service.
4. This RFC does not claim regulatory capital model approval.
5. This RFC does not approve unrestricted enterprise production rollout by itself.
6. This RFC does not require `ACTIVE_RISK + ISSUER` support until upstream benchmark issuer exposure semantics exist and are approved.

## Decision

`lotus-risk` will be treated as a credible private-banking risk analytics domain service with a defined enterprise-readiness runway.

The service may be used for controlled internal, advisory, and Workbench risk workflows where:

1. supported endpoints and modes are used,
2. API contracts are consumed as documented,
3. attribution residuals are surfaced truthfully,
4. issuer active-risk attribution is not represented as supported,
5. operational dependency states are considered during rollout.

The service must not be labeled fully enterprise-bank production-ready until the remaining slices in this RFC are complete.

## Current Validated Analytics Baseline

The following endpoint families are implemented and live-validated for the canonical portfolio `PB_SG_GLOBAL_BAL_001` as of the current validation pass.

| Endpoint / Capability | Current Status | Live Validation Notes |
| --- | --- | --- |
| `POST /analytics/risk/calculate` volatility | Implemented and live-validated | Uses trading-day observations and annualizes on trading-day basis. |
| `POST /analytics/risk/calculate` Sharpe | Implemented and live-validated | Risk-free handling is explicit; methodology uses excess return over volatility. |
| `POST /analytics/risk/calculate` Sortino | Implemented and live-validated | Downside deviation is measured relative to MAR. |
| `POST /analytics/risk/calculate` beta | Implemented and live-validated | Uses covariance of portfolio and benchmark returns over benchmark variance. |
| `POST /analytics/risk/calculate` tracking error | Implemented and live-validated | Uses active returns and trading-day annualization. |
| `POST /analytics/risk/calculate` information ratio | Implemented and live-validated | Uses annualized active return over tracking error. |
| `POST /analytics/risk/calculate` VaR | Implemented and live-validated | `HISTORICAL`, `GAUSSIAN`, and `CORNISH_FISHER` validated; output is a signed return threshold in percentage points. |
| `POST /analytics/risk/drawdown` | Implemented and live-validated | Drawdown series is reconciled on trading-day returns. |
| `POST /analytics/risk/concentration` | Implemented and live-validated | Stateful concentration and simulation concentration are validated. |
| `POST /analytics/risk/historical-attribution` total risk | Implemented and live-validated | Exposure history is aligned to trading-day return observations. |
| `POST /analytics/risk/historical-attribution` active risk | Implemented and live-validated for supported dimensions | `POSITION`, `SECTOR`, and `ASSET_CLASS` are supported; `ISSUER` is intentionally unsupported. |
| `POST /analytics/risk/rolling-metrics` | Implemented and live-validated | Rolling volatility, Sharpe, beta, tracking error, information ratio, max drawdown, multi-window, time-series, and partial-window behavior validated. |

## Trading-Day Methodology Baseline

The service must compute realized historical risk metrics on trading-day observations, not calendar-day counts.

The current canonical live YTD validation path receives 90 calendar observations from upstream performance data and filters them to 64 trading-day observations before risk calculation.

This affects:

1. volatility,
2. Sharpe,
3. Sortino,
4. beta,
5. tracking error,
6. information ratio,
7. VaR where the return sample is used,
8. drawdown where return chronology matters,
9. historical attribution where exposure rows must align to return dates,
10. rolling metrics where window counts must reflect observations, not calendar days.

This behavior is a permanent methodology requirement. Reintroducing calendar-day observation assumptions would be a correctness regression.

## VaR Interpretation Decision

VaR and expected shortfall are reported as signed return thresholds in percentage points.

Implications:

1. negative values indicate loss-threshold returns,
2. positive values can be valid when the empirical or parametric lower tail remains positive for the selected period,
3. downstream UI and reporting must not relabel positive VaR as a positive loss amount,
4. if a consumer wants positive-loss convention, it must explicitly transform and label the value.

This decision supports private-banking transparency and avoids misleading risk presentation.

## Historical Attribution Decision

Historical attribution is an explainability surface, not a guarantee that every grouping is fully additive.

For active-risk attribution:

1. `total_value` is the annualized active-return tracking error,
2. contributor rows are covariance-based explainability components,
3. `reconciled_sum` is the sum of displayed contributor effects,
4. `residual` is the unexplained amount after the chosen grouping is applied,
5. consumers must display `reconciled_sum` and `residual` together.

A material residual is not automatically a calculation defect. It can be a truthful result when the selected grouping does not fully explain active-risk dynamics.

## Intentional Limitation: ACTIVE_RISK + ISSUER

`historical-attribution` stateful `ACTIVE_RISK + ISSUER` remains intentionally unsupported.

This is not a temporary accidental defect in `lotus-risk`.

The reason is methodological and contractual:

1. stateful issuer active-risk attribution requires benchmark issuer exposure history over the requested period,
2. that benchmark issuer exposure history must be aligned to benchmark returns,
3. issuer mapping must be canonical and audit-ready,
4. issuer hierarchy semantics must be explicit, including direct issuer versus ultimate parent behavior,
5. the exposure contract must reconcile with portfolio issuer exposure semantics.

Current supported active-risk grouping dimensions are:

1. `POSITION`,
2. `SECTOR`,
3. `ASSET_CLASS`.

Current intentionally unsupported active-risk grouping dimension:

1. `ISSUER`.

Required behavior:

1. `lotus-risk` must reject unsupported `ACTIVE_RISK + ISSUER` requests deterministically at the request boundary,
2. OpenAPI and domain documentation must continue to document this limitation,
3. no downstream UI should present issuer active-risk attribution as available,
4. future issuer support requires a separate RFC or approved slice once upstream issuer benchmark exposure semantics exist.

## Enterprise Readiness Assessment

### Strong Areas

`lotus-risk` is strong in these areas:

1. core risk metric implementation,
2. stateful sourcing through the correct bounded contexts,
3. trading-day methodology correction,
4. deterministic unsupported-mode behavior,
5. live reconciliation against canonical platform data,
6. meaningful unit and integration coverage,
7. OpenAPI and domain documentation quality,
8. concentration simulation support where simulation is methodologically valid.

### Not Yet Fully Enterprise-Ready

`lotus-risk` still requires additional proof in these areas:

1. upstream resilience under timeout, retry, and partial failure conditions,
2. canonical URL enforcement across local, Docker, ingress, CI, and deployed environments,
3. multi-portfolio live validation breadth,
4. audit lineage and calculation reproducibility,
5. production observability proof,
6. cross-service readiness and degraded-state validation,
7. final model-governance documentation and sign-off.

## Enterprise Readiness State Model

This RFC defines four readiness states for `lotus-risk`.

### State 1: Technically Running

Characteristics:

1. service starts,
2. health endpoints respond,
3. basic analytics requests return responses.

This state is not sufficient for bank usage.

### State 2: Analytics Credible

Characteristics:

1. core metrics compute correctly for supported inputs,
2. methodology documentation exists,
3. unit and integration tests cover major behavior,
4. canonical portfolio live validation passes.

`lotus-risk` is currently at least in this state.

### State 3: Controlled Banking Workflow Ready

Characteristics:

1. supported endpoint modes are final and documented,
2. unsupported behavior is deterministic,
3. canonical upstream sourcing is enforced,
4. live validation covers key Workbench and advisory workflows,
5. operational dependency status is visible enough for controlled rollout.

`lotus-risk` is close to this state for the validated canonical workflow.

### State 4: Enterprise Production Approved

Characteristics:

1. dependency resilience has been proven under failure scenarios,
2. observability covers latency, failure classes, execution modes, and degraded states,
3. audit lineage is complete and reproducible,
4. multi-portfolio and edge-case validation is complete,
5. cross-service URL and environment governance is enforced,
6. model governance and business sign-off are complete.

`lotus-risk` is not yet in this state.

## Required Future Slices

### Slice 1: Dependency Resilience and Failure Classification

Goal:
prove that `lotus-risk` behaves deterministically under upstream failure.

Required work:

1. test lotus-core timeout behavior,
2. test lotus-performance timeout behavior,
3. test retryable 502/503/504 behavior,
4. test non-retryable 400/404/422 upstream behavior,
5. verify deterministic Lotus error codes and messages,
6. verify correlation ID propagation through upstream failure responses,
7. document endpoint-specific degraded behavior.

Exit criteria:

1. upstream failure matrix exists,
2. tests cover every dependency and major endpoint family,
3. `/health/ready` and `/ops` report dependency state coherently,
4. no raw upstream exception leaks to clients.

### Slice 2: Canonical URL and Environment Governance

Goal:
make service-to-service routing hard to misconfigure.

Required work:

1. inventory canonical `lotus-core`, `lotus-performance`, and `lotus-risk` URLs across local Docker and ingress,
2. validate environment variables in startup/config tests,
3. detect common port-confusion mistakes where possible,
4. document canonical local live validation commands,
5. ensure live tests default to canonical direct service URLs,
6. ensure Docker examples and runtime docs match actual service ownership.

Exit criteria:

1. local and Docker URL contract tests pass,
2. docs have one clear canonical path,
3. no known doc points users to the wrong service for performance integration APIs.

### Slice 3: Multi-Portfolio Live Validation Matrix

Goal:
prove analytics beyond one canonical balanced portfolio.

Required portfolio archetypes:

1. balanced global portfolio,
2. equity-heavy portfolio,
3. fixed-income-heavy portfolio,
4. cash-heavy portfolio,
5. multi-currency portfolio,
6. short-history portfolio,
7. sparse or missing benchmark portfolio,
8. high-concentration portfolio.

Required endpoint coverage:

1. risk calculate,
2. drawdown,
3. concentration,
4. rolling metrics,
5. historical attribution for supported dimensions.

Exit criteria:

1. a live validation matrix is committed,
2. failures are either fixed or documented as governed limitations,
3. each endpoint has at least one edge-case live proof.

### Slice 4: Audit Lineage and Model-Governance Evidence

Goal:
make risk results reproducible and model-reviewable.

Required work:

1. standardize calculation IDs or request fingerprints across endpoints,
2. expose source service and source contract versions consistently,
3. expose observation windows and alignment policies consistently,
4. document methodology version per metric family,
5. add reproducibility notes for live validation data,
6. identify what evidence should be persisted by downstream reporting workflows.

Exit criteria:

1. model-validation reviewer can trace output to source data and methodology,
2. every endpoint exposes enough lineage to support audit review,
3. methodology docs and API metadata agree.

### Slice 5: Production Observability Proof

Goal:
prove the service is operable in production.

Required signals:

1. upstream latency by dependency and operation,
2. upstream failure class,
3. endpoint execution mode,
4. calculation duration,
5. observation counts,
6. coverage ratios,
7. degraded or partial result conditions,
8. correlation ID propagation.

Exit criteria:

1. metrics and logs are verified for representative successful and failing requests,
2. dashboards or operator docs identify the key signals,
3. alerting recommendations are documented for dependency degradation and calculation failures.

### Slice 6: Gateway and Product-Surface Alignment

Goal:
ensure Workbench and other consumers present risk results truthfully.

Required work:

1. verify `lotus-gateway` does not transform signed VaR into misleading loss labels,
2. verify attribution residuals are passed through and displayed clearly,
3. verify unsupported issuer active-risk attribution is not exposed in UI affordances,
4. verify concentration simulation is the only simulation flow presented for current risk analytics,
5. validate canonical Workbench risk panels against the final API contract.

Exit criteria:

1. no UI feature claims unsupported backend capability,
2. labels and explanations match methodology docs,
3. gateway contract remains aligned with `lotus-risk` OpenAPI.

## Current Evidence

The current implementation and validation pass includes:

1. `make check` passing in `lotus-risk`, including lint, format, no-alias, mypy, OpenAPI quality, vocabulary inventory, and unit tests,
2. live `risk/calculate` characterization passing for selected metrics and all VaR methods,
3. live `historical-attribution` characterization passing for total risk and supported active-risk dimensions,
4. live `rolling-metrics` characterization passing for selected rolling metrics, Sharpe, multi-window, time-series, and partial-window behavior,
5. live concentration characterization passing,
6. contract and OpenAPI example updates for trading-day counts,
7. domain API documentation updates for risk calculate, rolling metrics, historical attribution, and VaR methodology.

## API Contract Expectations

The supported mode contract remains:

| Endpoint | Stateless | Stateful | Simulation | Notes |
| --- | --- | --- | --- | --- |
| `risk/calculate` | Supported | Supported | Unsupported | Historical realized risk metrics only. |
| `drawdown` | Supported | Supported | Unsupported | Historical realized drawdown only. |
| `concentration` | Supported | Supported | Supported | Simulation is methodologically valid for projected holdings/exposures. |
| `rolling-metrics` | Supported | Supported | Unsupported | Historical rolling diagnostics only. |
| `historical-attribution` | Supported | Supported | Unsupported | Historical attribution only; active issuer grouping intentionally unsupported statefully. |

## Upstream Ownership Model

The service ownership boundaries remain:

1. `lotus-risk` owns risk analytics calculations and risk API contracts,
2. `lotus-performance` owns portfolio and benchmark return series for performance-aligned analytics,
3. `lotus-performance` exposes benchmark exposure context for supported active-risk dimensions as a derived, lineage-backed performance-aligned view,
4. `lotus-core` owns portfolio, position, issuer, instrument, benchmark composition, and reference-data authority,
5. `lotus-core` owns risk-free reference series sourcing,
6. `lotus-gateway` owns experience composition and must not invent unsupported risk capability.

## Acceptance Criteria for Enterprise Production Approval

`lotus-risk` can be called enterprise-bank production-approved only when all of the following are true:

1. all required future slices in this RFC are complete,
2. CI and local repo-native gates pass,
3. live validation matrix covers multiple portfolio archetypes,
4. dependency failure behavior is deterministic and documented,
5. observability proof exists for success, failure, and degraded dependency states,
6. audit lineage is sufficient for model-review and operational investigation,
7. downstream gateway and Workbench surfaces preserve supported/unsupported behavior truthfully,
8. `ACTIVE_RISK + ISSUER` remains documented as unsupported unless a future approved issuer-exposure contract changes that state.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Teams mistake canonical portfolio success for full enterprise readiness | This RFC defines readiness states and future slices. |
| UI mislabels signed VaR as a positive loss amount | VaR methodology and gateway/product checks must preserve signed return-threshold semantics. |
| Attribution residuals are hidden or misunderstood | API docs and UI must show `reconciled_sum` and `residual` together. |
| Unsupported issuer active-risk is accidentally exposed | Keep request validation, OpenAPI docs, and UI affordances aligned to the explicit limitation. |
| Dependency misconfiguration causes false failures | Add canonical URL and environment governance tests and docs. |
| Operational incidents are hard to diagnose | Add metrics, logs, dependency-state reporting, and correlation propagation proof. |

## Implementation Status

Implemented in the current validation branch:

1. trading-day stateful return filtering,
2. live metric reconciliation expansion,
3. live concentration simulation serialization fix,
4. historical attribution exposure-to-return-date alignment,
5. rolling multi-window and partial-window live characterization,
6. OpenAPI example updates for 64 trading-day observations,
7. methodology documentation for signed VaR output,
8. domain documentation for supported active attribution dimensions and intentional issuer limitation.

Not yet implemented:

1. full dependency failure matrix,
2. canonical URL enforcement across all environments,
3. multi-portfolio live validation matrix,
4. full audit lineage standardization,
5. production observability proof,
6. gateway and Workbench product-surface validation against this final posture.

## Open Questions

1. Which additional seeded portfolios should be canonical for the multi-portfolio live validation matrix?
2. Should issuer active-risk attribution remain permanently out of scope, or should a future RFC define benchmark issuer exposure semantics?
3. Should calculation lineage be persisted by `lotus-risk`, `lotus-gateway`, or downstream reporting workflows?
4. What operational SLOs should apply to risk analytics latency by endpoint family?

## Conclusion

`lotus-risk` is credible for controlled private-banking risk analytics workflows and has strong evidence for the canonical portfolio path.

It should be treated as:

1. analytically credible for supported endpoints,
2. near controlled-workflow readiness,
3. not yet fully enterprise-bank production-approved.

The intentional `ACTIVE_RISK + ISSUER` limitation remains part of the contract until upstream benchmark issuer exposure semantics are available and explicitly approved.

The next highest-value work is not another metric. It is enterprise hardening: dependency resilience, canonical URL governance, broader live validation, audit lineage, observability proof, and product-surface alignment.
