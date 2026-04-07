# RFC-0007 - Final Production Readiness and Integration Hardening for lotus-risk

| Field | Value |
| --- | --- |
| Status | Draft, approved direction; Slice 1 and Slice 2 in progress on feature branch |
| Created | 2026-04-07 |
| Last Updated | 2026-04-07 |
| Owners | lotus-risk |
| Depends On | lotus-core, lotus-performance |
| Related Standards | lotus-platform RFC-0067, RFC-0003, RFC-0005, RFC-0006 |
| Scope | Cross-repo |
| Implementation Classification | Partially implemented (requires enhancement) |

## Executive Summary

`lotus-risk` is materially stronger than before: the implemented endpoint surface is credible, the stateful integrations are real, and the test stack is substantially improved. It is not yet correct to call the service fully gold-standard or production-ready.

The remaining work is no longer about adding arbitrary features. It is about finishing the contract, removing ambiguity, aligning upstream ownership to bounded contexts, hardening integration behavior, and proving readiness with evidence.

This RFC defines that final readiness program and requests approval on the architectural decisions now clarified through implementation work:

1. Simulation exists only where it is methodologically valid.
2. Benchmark return history is sourced from `lotus-performance`.
3. Risk-free reference series is sourced from `lotus-core`.
4. Benchmark exposure history for stateful active-risk attribution is sourced from `lotus-core`.
5. `lotus-risk` remains the analytics owner and orchestration layer; it does not become a portfolio-construction or market-data ownership service.

## Original Requested Requirements (Preserved)

The remaining readiness work discussed for `lotus-risk` was:

1. Close explicit functional gaps.
2. Fully harden integrations with `lotus-core` and `lotus-performance`.
3. Resolve the known upstream dependency gap affecting rolling Sharpe.
4. Run broader end-to-end validation, not only targeted suites.
5. Finalize endpoint contracts and documentation so supported and unsupported modes are explicit.
6. Improve observability to production-grade quality.
7. Complete final cleanup and governance before calling the service production-ready.

The specific blockers identified were:

1. unresolved upstream dependency for rolling Sharpe risk-free data
2. final decision and documentation on unsupported modes
3. full pre-merge gate and live integrated validation
4. stateful active-risk attribution dependency on benchmark exposure history

The user also clarified two upstream ownership expectations that this RFC must honor:

1. benchmark returns should come from `lotus-performance`
2. risk-free series should come from `lotus-core`

## Current Implementation Reality

### Working and materially credible today

1. Operational endpoints are implemented and working:
   - `GET /health`
   - `GET /health/live`
   - `GET /health/ready`
   - `GET /metadata`
   - `GET /ops`
   - `GET /integration/capabilities`
   - `GET /openapi.json`
   - `GET /metrics`
2. Analytical endpoints are implemented and in active use:
   - `POST /analytics/risk/calculate`
   - `POST /analytics/risk/drawdown`
   - `POST /analytics/risk/concentration`
   - `POST /analytics/risk/rolling-metrics`
   - `POST /analytics/risk/historical-attribution`
3. Stateful integration is materially improved:
   - canonical stateful returns-series request construction
   - explicit longest-window sourcing for required periods
   - stronger upstream error surfacing
   - improved Docker/runtime URL handling
   - better characterization, contract, integration, and smoke coverage
4. Simulation is correctly implemented only where it is naturally valid today:
   - `POST /analytics/risk/concentration`

### Explicitly incomplete or intentionally unsupported today

1. `risk/calculate` does not support simulation.
2. `drawdown` does not support simulation.
3. `rolling-metrics` does not support simulation.
4. `historical-attribution` does not support simulation.
5. `historical-attribution` stateful `ACTIVE_RISK` now uses lotus-core decomposed benchmark contracts for `POSITION`, `SECTOR`, and `ASSET_CLASS`.
6. `historical-attribution` stateful `ACTIVE_RISK` + `ISSUER` remains gated until benchmark issuer exposure semantics are explicitly available.
7. Some docs still reflect an older assumption that stateful risk-free series comes from `lotus-performance`; this is not the target architecture.

## Requirement-to-Implementation Traceability

| Requirement | Current State | Evidence / Basis | Outcome |
| --- | --- | --- | --- |
| Support simulation only where methodologically valid | Achieved in principle, not yet fully codified in all contracts/docs | Concentration RFC and live implementation; no valid time-series simulation methodology approved for other endpoints | Keep and formalize |
| Benchmark returns should come from `lotus-performance` | Achieved in current stateful rolling/risk design direction | lotus-performance returns-series contract and integration usage | Confirm and preserve |
| Risk-free series should come from `lotus-core` | Implemented on feature branch for stateful rolling Sharpe | rolling adapter now sources risk-free reference series through lotus-core risk-free contract | Validate live |
| Stateful active-risk attribution needs benchmark exposure history | Implemented on feature branch for POSITION, SECTOR, and ASSET_CLASS via decomposed contracts | lotus-core benchmark assignment, market-series, and index catalog contracts | Issuer active-risk remains open |
| Unsupported modes must be explicit and deterministic | Partially true, not final everywhere in docs/contracts | simulation reserved/rejected in some RFCs but not yet finalized across all endpoint docs/OpenAPI | Open |
| Production hardening of upstream behavior | Improved, not complete | better runtime wiring and tests exist, but no final service-wide readiness sign-off | Open |
| Full integrated validation against real upstreams | Partial | targeted live validations performed, not yet final full-gate sign-off | Open |
| Production-grade observability | Partial | correlation/error propagation improved, but final dependency/readiness instrumentation still needs confirmation | Open |

## Design Reasoning and Trade-offs

### 1. Simulation must remain methodology-driven, not symmetry-driven

The service should not expose simulation just because other endpoints do. For concentration, simulation is legitimate because the metric is a function of current/projected holdings and exposures.

For `risk/calculate`, `drawdown`, `rolling-metrics`, and `historical-attribution`, the current metric sets are primarily functions of realized historical time series. A projected holdings snapshot from `lotus-core` does not by itself generate a valid realized historical return path.

Trade-off:

1. fewer superficially symmetric API modes
2. better methodological integrity and lower risk of misleading analytics

Decision:

1. concentration keeps `stateless + stateful + simulation`
2. the other analytics endpoints keep `stateless + stateful` only in the current production contract

### 2. Upstream ownership must follow bounded context, not implementation convenience

Benchmark return history belongs with the service that computes and serves performance series: `lotus-performance`.

Risk-free series is reference/market data and therefore belongs with `lotus-core`.

Trade-off:

1. `lotus-risk` may need to orchestrate more than one upstream for a single endpoint
2. the resulting architecture is cleaner, more scalable, and less likely to create ownership drift later

Decision:

1. portfolio returns: `lotus-performance`
2. benchmark returns: `lotus-performance`
3. risk-free series: `lotus-core`
4. benchmark exposure history for stateful active-risk attribution: `lotus-core`

### 3. Production readiness must be evidence-based

A service is not production-ready because the happy paths work locally. It is production-ready when:

1. contracts are final
2. supported and unsupported modes are explicit
3. upstream failures are deterministic and diagnosable
4. documentation matches runtime truth
5. full validation evidence exists

This RFC therefore defines exit criteria instead of relying on qualitative judgment.

## Gap Assessment

### Gap A: Unsupported modes are not yet fully codified as final contract

Current reality is already clear enough to make the decision:

1. `risk/calculate`: `stateless + stateful` only
2. `drawdown`: `stateless + stateful` only
3. `rolling-metrics`: `stateless + stateful` only
4. `historical-attribution`: `stateless + stateful` only in current scope

The gap is not design uncertainty. The gap is contract finalization.

Required action:

1. hard-reject unsupported modes
2. update OpenAPI and domain docs to remove ambiguity

### Gap B: Stateful rolling Sharpe still needs risk-free sourcing alignment

The current implementation already proves that `lotus-risk` can:

1. detect that `ROLLING_SHARPE` requires risk-free data
2. resolve reporting currency when caller omitted it
3. surface deterministic failure when required risk-free data is absent

What remains is architectural alignment and live validation:

1. stateful risk-free series should come from `lotus-core`
2. that path must be validated against real upstream data for supported currencies and periods

This is not just a data-seeding issue. It is also a contract-ownership alignment issue.

### Gap C: Stateful active-risk attribution still needs issuer benchmark semantics

The original blocker was benchmark exposure history. lotus-core confirms this is provided through a decomposed benchmark contract family rather than a monolithic benchmark exposure endpoint.

For `POSITION`, `SECTOR`, and `ASSET_CLASS`, lotus-risk can derive benchmark exposure history from:

1. benchmark assignment
2. benchmark market-series component weights
3. index catalog classification labels

The remaining gap is issuer-level active attribution. `lotus-risk` still needs benchmark issuer exposure semantics before it can support `ACTIVE_RISK` + `ISSUER` statefully.

For issuer support, `lotus-risk` does not merely need benchmark metadata or current benchmark composition. It needs benchmark issuer exposure history over time:

1. over the requested period
2. at the supported grouping dimensions
3. in canonical Lotus vocabulary
4. with semantics aligned to portfolio exposure history
5. in a shape that supports deterministic reconciliation and auditability

Until that issuer-specific mapping exists, stateful issuer active-risk attribution remains gated.

### Gap D: Operational hardening is improved but not complete

The recent branch work materially improved integration reliability, but the service still needs final evidence for:

1. timeout and retry policy by dependency and failure class
2. deterministic Lotus error mapping for all major upstream failures
3. canonical URL handling across environments
4. dependency readiness/degraded-state surfacing
5. service-wide observability coverage

## Deviations and Evolution Since Earlier RFCs

1. Earlier rolling-risk materials assumed risk-free series would be sourced alongside returns from `lotus-performance`.
   - That assumption is now superseded.
   - The target architecture is risk-free from `lotus-core`.
2. Earlier endpoint language sometimes kept simulation as a future placeholder on time-series endpoints.
   - That ambiguity should now be removed.
   - Unsupported simulation should be explicit in the production contract.
3. Historical attribution RFC wording already acknowledged benchmark exposure-history dependency.
   - This RFC promotes the residual issuer-level dependency to a top-level production-readiness gate.

## Proposed Changes

### A. Finalize endpoint mode contracts

1. `POST /analytics/risk/concentration`
   - support: `stateless`, `stateful`, `simulation`
2. `POST /analytics/risk/calculate`
   - support: `stateless`, `stateful`
   - reject: `simulation`
3. `POST /analytics/risk/drawdown`
   - support: `stateless`, `stateful`
   - reject: `simulation`
4. `POST /analytics/risk/rolling-metrics`
   - support: `stateless`, `stateful`
   - reject: `simulation`
5. `POST /analytics/risk/historical-attribution`
   - support: `stateless`, `stateful`
   - reject: `simulation`
   - support stateful `ACTIVE_RISK` for `POSITION`, `SECTOR`, and `ASSET_CLASS`
   - gate stateful `ACTIVE_RISK` + `ISSUER` until benchmark issuer semantics are validated

### B. Align upstream sourcing model

1. Portfolio returns: `lotus-performance`
2. Benchmark returns: `lotus-performance`
3. Risk-free series: `lotus-core`
4. Benchmark exposure history: `lotus-core` via benchmark assignment, benchmark market-series, and index catalog classification labels

### C. Complete integration hardening

1. tighten timeout budgets
2. define retry policy by failure class
3. standardize deterministic upstream failure mapping
4. confirm canonical URL/config handling in all target environments
5. strengthen readiness/degraded dependency reporting

### D. Finalize docs and OpenAPI

1. supported modes must be explicit
2. unsupported modes must be explicit
3. gated modes must be explicit
4. upstream ownership by endpoint must be explicit
5. examples must reflect actual current integrated behavior

### E. Complete production-readiness validation

1. full branch-wide lint/unit/integration/e2e gate
2. Docker build/runtime validation
3. live endpoint-by-endpoint validation against current `lotus-core` and `lotus-performance`
4. PR/CI evidence before merge

## Test and Validation Evidence Required

This RFC should not be marked implemented based on intent alone. The required evidence set is:

1. contract tests proving unsupported modes fail deterministically
2. integration tests proving stateful upstream request shape and error mapping
3. endpoint-level tests for risk-free-backed rolling Sharpe behavior after migration to `lotus-core`
4. endpoint-level tests for stateful active-risk attribution through decomposed benchmark contracts
5. full local gate results:
   - lint
   - unit
   - integration
   - e2e
   - Docker build/runtime
6. live validation evidence for the implemented endpoint surface against real upstream services

## Original Acceptance Criteria Alignment

| Original Acceptance Need | Alignment Target |
| --- | --- |
| Close functional gaps | Final mode contract and upstream dependency closure |
| Harden integrations | deterministic upstream behavior, timeout/retry policy, canonical URL handling |
| Resolve rolling Sharpe dependency | migrate risk-free sourcing to `lotus-core` and validate live |
| Broader end-to-end validation | full gate plus real upstream Docker/live validation |
| Finalize docs and contracts | OpenAPI and domain docs match runtime truth |
| Production-grade observability | latency, failure-class, execution-mode, degraded-state visibility |
| Cleanup and governance | no stale assumptions, RFC-0067 alignment, PR/CI proof before merge |

## Rollout and Backward Compatibility

1. No new legacy aliases should be introduced.
2. Unsupported modes should fail explicitly rather than being silently accepted or ambiguously reserved.
3. Documentation corrections should ship with contract changes.
4. If any client currently assumes stateful risk-free sourcing from `lotus-performance`, that assumption must be corrected through documentation and release notes before the aligned implementation ships.

## Open Questions

1. What exact benchmark issuer exposure semantics should be used for stateful `ACTIVE_RISK` + `ISSUER` attribution?
2. Which exact `lotus-core` risk-free contract should be the canonical integration point for rolling Sharpe and any future risk-free-backed stateful metrics?
3. Do we want unsupported-mode responses standardized on one specific Lotus error code across all analytics endpoints, or is the current per-endpoint validation mapping sufficient as long as it is deterministic and documented?

## Approval Decisions Requested

1. Approve the final upstream ownership model:
   - benchmark returns from `lotus-performance`
   - risk-free series from `lotus-core`
   - benchmark exposure history from `lotus-core`
2. Approve the final mode policy:
   - simulation remains concentration-only in the current `lotus-risk` production surface
   - `risk/calculate`, `drawdown`, `rolling-metrics`, and `historical-attribution` do not expose simulation in the current contract
3. Approve hard rejection of unsupported modes.
4. Approve `historical-attribution` stateful `ACTIVE_RISK` support for `POSITION`, `SECTOR`, and `ASSET_CLASS`, with `ISSUER` remaining gated until benchmark issuer exposure semantics are available.

## Next Actions

### P0

1. Verify the canonical `lotus-core` risk-free contract and migrate stateful rolling Sharpe to it.
2. Verify benchmark issuer exposure semantics needed for stateful issuer active-risk attribution.
3. Finalize endpoint contracts and OpenAPI so unsupported modes are explicit.

### P1

1. Complete service-wide integration hardening for timeout, retry, and upstream failure mapping.
2. Update domain docs, endpoint matrix, and capability docs to reflect the final upstream ownership split.
3. Strengthen observability for dependency readiness, latency, and degraded-state reporting.

### P2

1. Run full local branch-wide gate.
2. Run live Docker endpoint-by-endpoint validation against current upstream services.
3. Open PR, drive CI to green, and merge only after the evidence set is complete.

## Operational Exit Criteria

`lotus-risk` may be called gold-standard and production-ready only when all of the following are true:

1. All supported endpoint modes are explicitly documented and enforced.
2. Unsupported modes fail deterministically and are documented as unsupported.
3. Stateful rolling Sharpe uses `lotus-core` risk-free sourcing and passes live validation for supported currencies and windows.
4. Stateful `ACTIVE_RISK` attribution is either:
   - fully integrated and validated, or
   - explicitly unavailable for unsupported grouping dimensions with no ambiguity in the contract and a clearly documented upstream dependency gate
5. Full lint/unit/integration/e2e/Docker gates pass on the final branch.
6. Live endpoint-by-endpoint validation passes against current upstream services.
7. OpenAPI and domain documentation reflect actual runtime behavior.
8. Observability and correlation standards are verified.
9. Canonical URLs and environment configuration are proven across expected runtime environments.
10. Final PR and CI evidence are green before merge.
