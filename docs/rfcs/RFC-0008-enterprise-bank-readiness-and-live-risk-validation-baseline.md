# RFC-0008: Enterprise Bank Readiness and Live Risk Validation Baseline

- Status: Proposed
- Date: 2026-04-13
- Owners: lotus-risk
- Requires Approval From: lotus-risk maintainers, lotus-platform maintainers
- Depends On: lotus-core, lotus-performance, lotus-gateway, lotus-workbench, lotus-platform
- Related Standards: lotus-platform RFC-0067, RFC-0071, RFC-0072, RFC-0073; lotus-risk RFC-0003, RFC-0004, RFC-0005, RFC-0006, RFC-0007
- Implementation Classification: enterprise-readiness program; current analytics baseline is validated for canonical portfolio, final enterprise production approval remains open

## Summary

`lotus-risk` is now credible as a private-banking risk analytics domain service for controlled Workbench and advisory workflows. The service has live evidence for the canonical portfolio `PB_SG_GLOBAL_BAL_001` across the major risk surfaces:

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

This RFC defines the final enterprise-readiness program required before `lotus-risk` should be called enterprise-bank production-approved.

The central decision is conservative:

1. `lotus-risk` is analytically credible for supported endpoints and modes,
2. `lotus-risk` is suitable for controlled private-banking workflow rollout when dependency posture is considered,
3. `lotus-risk` is not yet approved for unrestricted enterprise-bank production use,
4. final approval requires explicit hardening, observability, audit lineage, multi-portfolio validation, product-surface alignment, documentation, agent context review, and branch hygiene.

## Why This RFC Exists

Recent work proved that the core analytics are no longer merely synthetic-test complete. The service now reconciles live platform data for the canonical private-banking portfolio and exposes better contracts, examples, and methodology documentation.

That success creates a new risk: treating successful live calculation validation as full enterprise readiness.

For a bank, working analytics are necessary but not sufficient. Final readiness also requires:

1. deterministic dependency behavior,
2. canonical environment and URL governance,
3. broader live-data validation,
4. audit and model-governance evidence,
5. production observability,
6. truthful gateway and Workbench presentation,
7. durable documentation and agent guidance.

This RFC exists to prevent scope drift and define the remaining work as an explicit, slice-by-slice program.

## Problem Statement

`lotus-risk` can now produce credible risk analytics for the canonical portfolio, but enterprise-like banks need stronger guarantees than one canonical happy path.

Current gaps are:

1. upstream failure behavior is not fully proven under timeout, retry, unavailable, malformed, and partial-data conditions,
2. service URLs and environment variables are still easy to misconfigure, as shown by port confusion between lotus-core and lotus-performance during live validation,
3. live validation breadth is narrow compared with the portfolio archetypes a private bank manages,
4. audit lineage is not yet uniformly sufficient for model-review and reproducibility,
5. observability has not been proven end-to-end for success, failure, and degraded states,
6. downstream gateway and Workbench surfaces still need explicit validation against signed VaR, attribution residual, and unsupported-mode semantics,
7. reusable agent guidance should be reviewed so future work starts from the current truth rather than rediscovering it.

## Goals

1. Define the enterprise-readiness target state for `lotus-risk`.
2. Preserve the current live-validated analytics baseline with concrete evidence expectations.
3. Make trading-day calculations a permanent methodology requirement.
4. Keep `ACTIVE_RISK + ISSUER` intentionally unsupported until benchmark issuer exposure semantics exist.
5. Define implementation slices with clear acceptance criteria.
6. Require documentation, agent context, skills guidance assessment, and branch hygiene as a final slice.
7. Make GitHub-backed asynchronous validation part of the implementation posture.

## Non-Goals

1. Add new risk metrics.
2. Claim regulatory market-risk capital model approval.
3. Move benchmark, portfolio, issuer, risk-free, or performance data ownership into `lotus-risk`.
4. Require `lotus-core` or `lotus-performance` changes in the first implementation slice.
5. Support `ACTIVE_RISK + ISSUER` without a separate approved issuer benchmark exposure contract.
6. Approve unrestricted production rollout by publishing this RFC.

## Decision

`lotus-risk` will proceed through a seven-slice enterprise-readiness program.

The service remains the risk analytics authority. It computes risk metrics and owns the risk API contract. It does not become a portfolio system, benchmark master, issuer hierarchy service, or market-data service.

The service may be treated as controlled-workflow ready only for explicitly supported endpoints, modes, and dimensions. Unsupported capabilities must fail deterministically and must not be exposed by downstream UI or gateway affordances.

Final enterprise-bank production approval requires completion of all slices and a clean PR/CI/merge loop.

## Readiness State Model

### State 1: Running

The service starts and returns basic health/API responses.

This state is not sufficient for banking use.

### State 2: Analytics Credible

The service computes supported analytics correctly for representative data and has methodology documentation, unit tests, integration tests, and live canonical portfolio evidence.

`lotus-risk` is currently in this state.

### State 3: Controlled Workflow Ready

The service can support controlled private-banking Workbench/advisory workflows because:

1. supported modes are final and documented,
2. unsupported modes are rejected deterministically,
3. dependency readiness is visible,
4. canonical workflow validation is green,
5. downstream product surfaces preserve analytical truth.

`lotus-risk` is close to this state but still needs the slices in this RFC.

### State 4: Enterprise Production Approved

The service can support enterprise-bank production traffic because:

1. dependency resilience is proven,
2. canonical URL governance is enforced,
3. multi-portfolio validation is complete,
4. audit lineage is complete enough for model review,
5. observability is proven,
6. gateway and Workbench surfaces are aligned,
7. documentation, context, and branch hygiene are complete.

`lotus-risk` is not yet in this state.

## Current Validated Baseline

| Capability | Status | Evidence Standard |
| --- | --- | --- |
| Volatility | Live-validated for canonical portfolio | Trading-day observations and 252-day annualization must reconcile. |
| Sharpe | Live-validated for canonical portfolio | Risk-free treatment must be explicit and documented. |
| Sortino | Live-validated for canonical portfolio | MAR and downside deviation behavior must reconcile. |
| Drawdown | Live-validated for canonical portfolio | Drawdown chronology must use trading-day returns. |
| Beta | Live-validated for canonical portfolio | Covariance over benchmark variance must reconcile. |
| Tracking error | Live-validated for canonical portfolio | Active returns and annualization must reconcile. |
| Information ratio | Live-validated for canonical portfolio | Annualized active return over tracking error must reconcile. |
| VaR | Live-validated for `HISTORICAL`, `GAUSSIAN`, `CORNISH_FISHER` | Output must be documented as signed percentage-point return threshold. |
| Concentration | Live-validated for stateful and simulation modes | Simulation change payloads must serialize JSON-safe dates. |
| Historical attribution total risk | Live-validated for supported grouping | Exposure rows must align to trading-day return dates. |
| Historical attribution active risk | Live-validated for `POSITION`, `SECTOR`, `ASSET_CLASS` | `ISSUER` remains intentionally unsupported. |
| Rolling risk | Live-validated for supported rolling metrics | Strict and partial windows must report counts and coverage truthfully. |

## Methodology Decisions

### Trading-Day Observations

Risk calculations must use trading-day observations, not calendar-day observation counts.

The canonical YTD live path receives 90 calendar observations from upstream performance data and filters them to 64 trading-day observations before risk calculation.

This is required for:

1. volatility,
2. Sharpe,
3. Sortino,
4. beta,
5. tracking error,
6. information ratio,
7. VaR,
8. drawdown,
9. historical attribution,
10. rolling metrics.

Reintroducing calendar-day assumptions is a methodology regression.

### VaR Output Semantics

VaR and expected shortfall are signed return thresholds in percentage points.

Required downstream behavior:

1. negative VaR means the selected lower-tail threshold is a loss return,
2. positive VaR is valid when the lower tail is still positive,
3. consumers must not label positive VaR as a positive loss amount,
4. any positive-loss convention must be an explicit downstream transformation.

### Historical Attribution Residuals

Historical attribution is explainability, not a guarantee of full additive decomposition for every grouping.

For active-risk attribution:

1. `total_value` is annualized active-return tracking error,
2. contributor rows are covariance-based explainability components,
3. `reconciled_sum` is the displayed contributor sum,
4. `residual` is the unexplained amount for the selected grouping,
5. consumers must present residual and reconciled sum together.

A material residual can be valid and must not be hidden.

## Intentional Limitation: ACTIVE_RISK + ISSUER

`historical-attribution` stateful `ACTIVE_RISK + ISSUER` is intentionally unsupported.

This limitation is part of the contract, not an accidental bug.

Issuer active-risk attribution requires benchmark issuer exposure history with these semantics:

1. periodized benchmark issuer exposure rows,
2. alignment to benchmark return dates,
3. canonical issuer identifiers,
4. explicit direct issuer versus ultimate parent rules,
5. classification semantics aligned to portfolio issuer exposure,
6. reconciliation metadata suitable for audit review.

Supported active-risk grouping dimensions:

1. `POSITION`,
2. `SECTOR`,
3. `ASSET_CLASS`.

Unsupported active-risk grouping dimension:

1. `ISSUER`.

Required behavior:

1. reject `ACTIVE_RISK + ISSUER` at request validation or deterministic contract boundary,
2. document the limitation in OpenAPI, domain docs, and product guidance,
3. prevent gateway and Workbench from exposing issuer active-risk controls,
4. require a future RFC or approved slice before enabling issuer support.

## API Mode Contract

| Endpoint | Stateless | Stateful | Simulation | Contract Decision |
| --- | --- | --- | --- | --- |
| `risk/calculate` | Supported | Supported | Unsupported | Historical realized risk only. |
| `drawdown` | Supported | Supported | Unsupported | Historical realized drawdown only. |
| `concentration` | Supported | Supported | Supported | Simulation is valid for projected holdings/exposures. |
| `rolling-metrics` | Supported | Supported | Unsupported | Historical rolling diagnostics only. |
| `historical-attribution` | Supported | Supported | Unsupported | Historical attribution only; stateful issuer active-risk unsupported. |

## Upstream Ownership Model

| Domain | Authoritative Owner | `lotus-risk` Responsibility |
| --- | --- | --- |
| Portfolio holdings and snapshots | lotus-core | Consume through governed core contracts. |
| Instrument and issuer reference data | lotus-core | Consume for concentration and enrichment-dependent analytics. |
| Portfolio returns | lotus-performance | Consume stateful returns series. |
| Benchmark returns | lotus-performance | Consume benchmark series with performance-aligned lineage. |
| Benchmark exposure context for supported active-risk dimensions | lotus-performance derived view backed by lotus-core lineage | Consume for active-risk attribution where supported. |
| Risk-free reference series | lotus-core | Consume for Sharpe and rolling Sharpe where required. |
| Risk calculations | lotus-risk | Compute, document, test, and expose risk analytics. |
| Product composition | lotus-gateway and lotus-workbench | Must not invent unsupported risk capability. |

## Requirement Traceability

| Requirement | Current State | Evidence / Expected Evidence | Outcome |
| --- | --- | --- | --- |
| Trading-day calculations | Implemented for current stateful risk-return path | Live reconciliation and OpenAPI example counts use 64 trading-day observations | Preserve and harden. |
| Live validation for canonical portfolio | Implemented for core endpoint families | Live characterization tests for risk, drawdown, concentration, attribution, rolling | Expand to portfolio matrix. |
| VaR method coverage | Implemented for three methods | Historical, Gaussian, and Cornish-Fisher live tests | Preserve and document signed semantics. |
| Concentration simulation | Implemented | Simulation payload serializes `effective_date` as JSON string | Preserve. |
| Active-risk supported dimensions | Implemented for `POSITION`, `SECTOR`, `ASSET_CLASS` | Live attribution tests | Preserve. |
| Active-risk issuer limitation | Intentional limitation | Request boundary rejection and docs | Keep until issuer benchmark exposure contract exists. |
| Dependency resilience | Partially implemented | Existing upstream clients classify some errors | Needs failure matrix. |
| Canonical URL governance | Partial | Defaults exist, but misconfiguration is still easy | Needs environment governance slice. |
| Audit lineage | Partial | Current metadata exists but is not uniform enough | Needs lineage slice. |
| Observability | Partial | Health/ops surfaces exist, full signal proof pending | Needs observability slice. |
| Product-surface alignment | Not complete in this repo | Requires gateway/workbench validation | Needs cross-repo validation slice. |
| Documentation and agent context | Partial | RFC and docs updated, context/skills review pending | Final slice required. |

## Implementation Slices

### Slice 1: Dependency Resilience and Failure Classification

Objective:
prove deterministic behavior under upstream failure.

Scope:

1. lotus-core timeout behavior,
2. lotus-performance timeout behavior,
3. retryable 502/503/504 responses,
4. non-retryable 400/404/422 responses,
5. malformed upstream payloads,
6. missing required upstream series,
7. partial upstream data.

Implementation expectations:

1. add reusable upstream failure fixtures,
2. avoid per-endpoint copy/paste failure tests where a shared pattern is possible,
3. verify Lotus error codes, messages, retryability, dependency names, and operation names,
4. verify correlation ID propagation.

Acceptance criteria:

1. no raw upstream exception leaks to clients,
2. failure classification is deterministic across endpoint families,
3. `/health/ready` and `/ops` present coherent dependency state,
4. tests cover representative failures for each upstream dependency.

### Slice 2: Canonical URL and Environment Governance

Objective:
make service routing hard to misconfigure.

Scope:

1. local direct service URLs,
2. Docker service URLs,
3. ingress URLs,
4. live-test defaults,
5. `.env.example` and runtime docs.

Implementation expectations:

1. inventory canonical URLs for `lotus-core`, `lotus-performance`, and `lotus-risk`,
2. add config contract tests for defaults and environment overrides,
3. document direct live validation URLs and known port ownership,
4. detect high-risk local mistakes where feasible, especially lotus-core query port versus lotus-performance analytics port.

Acceptance criteria:

1. config tests pass,
2. docs expose one canonical local validation path,
3. live-test defaults match actual service ownership,
4. no known `lotus-risk` doc points performance probes to lotus-core ports.

### Slice 3: Multi-Portfolio Live Validation Matrix

Objective:
prove analytics across a bank-relevant portfolio universe.

Minimum archetypes:

1. global balanced portfolio,
2. equity-heavy portfolio,
3. fixed-income-heavy portfolio,
4. cash-heavy portfolio,
5. multi-currency portfolio,
6. short-history portfolio,
7. sparse benchmark portfolio,
8. high-concentration portfolio.

Endpoint coverage:

1. `risk/calculate`,
2. `drawdown`,
3. `concentration`,
4. `rolling-metrics`,
5. `historical-attribution` for supported dimensions.

Acceptance criteria:

1. matrix is committed as documentation or generated evidence,
2. each archetype has expected supportability notes,
3. failures are either fixed or recorded as governed limitations,
4. canonical portfolio validation remains green.

### Slice 4: Audit Lineage and Model-Governance Evidence

Objective:
make outputs reproducible and model-reviewable.

Scope:

1. calculation/request fingerprinting,
2. source service metadata,
3. source contract versions,
4. observation windows,
5. alignment policy,
6. methodology version,
7. source series counts and coverage,
8. downstream evidence persistence expectations.

Acceptance criteria:

1. every endpoint exposes enough lineage to trace inputs and methodology,
2. methodology docs and API metadata agree,
3. model reviewer can reproduce or challenge a result from captured evidence,
4. gaps are documented with owners and priority.

### Slice 5: Production Observability Proof

Objective:
prove the service can be operated under production conditions.

Required signals:

1. upstream latency by dependency and operation,
2. upstream failure class,
3. endpoint execution mode,
4. calculation duration,
5. observation counts,
6. coverage ratios,
7. degraded or partial result conditions,
8. correlation ID propagation.

Acceptance criteria:

1. representative success and failure requests produce expected logs/metrics,
2. operator docs identify the key signals,
3. alerting recommendations exist for dependency degradation and calculation failure,
4. evidence can be used in PR review without relying on screenshots alone.

### Slice 6: Gateway and Product-Surface Alignment

Objective:
ensure downstream consumers preserve risk truth.

Scope:

1. `lotus-gateway` contract mapping,
2. Workbench risk panels,
3. signed VaR labels,
4. attribution residual display,
5. unsupported issuer active-risk affordances,
6. simulation mode affordances.

Acceptance criteria:

1. gateway does not transform signed VaR into misleading loss labels,
2. Workbench displays or preserves attribution residuals truthfully,
3. issuer active-risk is not offered as supported,
4. concentration is the only simulation-enabled risk flow in the current contract,
5. gateway and Workbench validation evidence is linked from the final implementation evidence.

### Slice 7: Documentation, Agent Context, Skills Guidance, and Branch Hygiene

Objective:
close the implementation with durable knowledge and clean repository state.

Scope:

1. update endpoint docs and methodology docs changed by prior slices,
2. update `REPOSITORY-ENGINEERING-CONTEXT.md` if repository truth changes,
3. update central Lotus context only if platform-wide routing, validation, or ownership truth changes,
4. assess whether any Lotus skills or guidance should change,
5. document the outcome of the skills/guidance assessment even if no changes are needed,
6. ensure RFC status and implementation evidence are current,
7. run repo-native gates,
8. push final branch state,
9. use GitHub checks asynchronously and fix forward promptly,
10. merge only after green checks and truthful evidence,
11. delete local and remote feature branch after merge if requested by the delivery workflow,
12. sync local `main` to remote `main`.

Skills and guidance assessment must explicitly consider:

1. whether `lotus-backend-delivery-governance` should mention trading-day validation for risk/performance analytics,
2. whether `lotus-methodology-doc-v3` should include signed-threshold guidance for risk metrics such as VaR,
3. whether `lotus-qa-platform-validator` should include a risk analytics live-validation matrix pattern,
4. whether central context should document canonical direct service ports for risk/performance/core live validation,
5. whether no skill/context change is warranted because the finding is repo-local.

Acceptance criteria:

1. docs and context are updated or explicitly assessed as unchanged,
2. branch is clean,
3. commits are small, meaningful, and truthful,
4. GitHub checks are green or failures are fixed forward,
5. final report lists validation commands, CI status, remaining limitations, and branch hygiene outcome.

## Validation Strategy

Use both local repo-native checks and GitHub asynchronous checks.

Minimum local checks per implementation slice:

1. targeted unit/integration tests for changed behavior,
2. `python -m ruff check` for touched files or full repo where appropriate,
3. `python -m mypy --config-file mypy.ini` when typing-sensitive code changes occur,
4. `make check` before final PR readiness.

GitHub strategy:

1. push the feature branch early,
2. monitor `Remote Feature Lane` checks while implementation continues,
3. inspect failing logs promptly,
4. fix forward with small commits,
5. do not claim CI is green unless GitHub reports green.

## Current Evidence

Current branch evidence includes:

1. `make check` passed locally after the live validation pass,
2. live `risk/calculate` characterization passed for selected metrics and all VaR methods,
3. live `historical-attribution` characterization passed for total risk and supported active-risk dimensions,
4. live `rolling-metrics` characterization passed for selected metrics, Sharpe, multi-window, time-series, and partial-window behavior,
5. live concentration characterization passed,
6. OpenAPI examples now reflect 64 trading-day observations,
7. VaR methodology documentation now describes signed return thresholds,
8. active-risk issuer limitation is documented as intentional,
9. Slice 1 now centralizes upstream error-detail extraction and documents deterministic failure categories for lotus-core and lotus-performance.

This evidence proves the current analytics baseline. It does not yet close the future enterprise-readiness slices.

## Acceptance Criteria for RFC Completion

This RFC is complete only when:

1. all seven implementation slices are complete,
2. the intentional `ACTIVE_RISK + ISSUER` limitation remains documented unless superseded by a future approved issuer-exposure contract,
3. local repo-native checks pass,
4. GitHub feature-lane and PR checks pass,
5. live validation matrix evidence is current,
6. docs, context, and skills/guidance assessment are complete,
7. branch and PR hygiene are complete.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Canonical portfolio validation is mistaken for full enterprise readiness | Keep readiness states and multi-portfolio slice explicit. |
| Signed VaR is mislabeled in UI or reporting | Preserve signed-threshold methodology and validate gateway/Workbench labels. |
| Attribution residuals are hidden | Require residual presentation in product-surface validation. |
| Unsupported issuer active-risk is accidentally exposed | Preserve request rejection, docs, and UI/gateway checks. |
| URL confusion causes false live-validation failures | Add canonical URL tests and docs. |
| Future agents rediscover known risk-specific patterns | Final slice must assess context and skill guidance. |
| CI failures are discovered late | Push early and monitor GitHub checks asynchronously. |

## Open Questions

1. Which additional seeded portfolios should become canonical for the live validation matrix?
2. Should issuer active-risk remain permanently unsupported, or should a future RFC define benchmark issuer exposure semantics?
3. Which service should persist calculation lineage for downstream audit evidence: `lotus-risk`, `lotus-gateway`, or reporting workflows?
4. What endpoint-level latency SLOs should apply to private-banking risk analytics?
5. Should platform context define canonical direct service ports for all live characterization tests, or should that remain repository-local?

## Conclusion

`lotus-risk` is analytically credible for supported private-banking risk workflows and has strong canonical live-data evidence.

It is not yet enterprise-bank production-approved.

The remaining path is clear: dependency resilience, canonical URL governance, multi-portfolio live validation, audit lineage, observability proof, gateway/product alignment, and final documentation/context/branch hygiene.

The `ACTIVE_RISK + ISSUER` limitation remains intentional and must stay documented until benchmark issuer exposure semantics are explicitly defined and approved.
