# Lotus Risk Issue Fix Closure Matrix

This matrix tracks the current `lotus-risk` issue-fix and enterprise refactor batch on branch
`refactor/enterprise-risk-backend`.

Parent ledger issue #159 remains open as the campaign ledger unless that issue itself is the target.
Each actionable issue is closed only when the implementation, same-pattern scan, tests, and
documentation/wiki/context decision are recorded.

| Issue | Title | Status | Fix surface | Same-pattern scan | Evidence |
| --- | --- | --- | --- | --- | --- |
| #195 | Prune or classify merged lotus-risk remote branches that still appear unmerged | Fixed locally | Remote branch hygiene | `origin/feat/sync-agent-operating-contract` was superseded because it would delete the target-repo-root rule; `origin/codex/sync-agent-operating-contract-20260704` had no diff from `origin/main`. Both remote branches were deleted. | `git branch -r --no-merged origin/main` returns no branches after prune. |
| #193 | Make cleanup scope match generated artifact and cache policy | Open | Generated artifact cleanup | Pending | Pending |
| #191 | Align risk observability domain API docs with monitoring contract | Open | Observability docs/API docs | Pending | Pending |
| #190 | Make endpoint execution metrics include response-model validation failures | Open | Endpoint metrics/error handling | Pending | Pending |
| #189 | Prove domain-data-product trust metadata against route response schemas | Open | Domain-product contracts/tests | Pending | Pending |
| #188 | Disambiguate API vocabulary semantic IDs for state, status, reason, and type fields | Open | API vocabulary inventory | Pending | Pending |
| #187 | Make proof evidence manifests stale-aware instead of pinning old PR metadata | Open | Proof artifacts | Pending | Pending |
| #186 | Bound position time-series pagination in historical attribution exposure sourcing | Open | Historical attribution upstream pagination | Pending | Pending |
| #185 | Reject invalid downstream timeout and pool overrides in enterprise mode | Open | Runtime configuration validation | Pending | Pending |
| #184 | Align PR-grade local CI targets with governed merge and main gates | Open | Makefile/GitHub workflows | Pending | Pending |
| #183 | Require executable body-limit proof for enterprise bank readiness | Open | HTTP boundary controls/tests | Pending | Pending |
| #182 | Separate API DTO contracts from core calculation domain models | Open | Architecture boundaries | Pending | Pending |
| #181 | Bound public upstream error messages in problem-details responses | Open | API error mapping/security | Pending | Pending |
| #180 | Make downstream client resolution a typed runtime composition boundary | Open | Runtime composition/dependencies | Pending | Pending |
| #179 | Map concentration lotus-core payload shape failures to upstream invalid responses | Open | Concentration upstream mapping | Pending | Pending |
| #178 | Preserve explicit empty projected positions in concentration simulation | Open | Concentration simulation semantics | Pending | Pending |
| #177 | Constrain concentration simulation transaction operation vocabulary | Open | Concentration simulation validation | Pending | Pending |
| #176 | Bound rolling metrics request fan-out and time-series response size | Open | Rolling metrics upstream pagination | Pending | Pending |
| #175 | Bound benchmark exposure pagination in stateful historical attribution | Open | Historical attribution benchmark exposure sourcing | Pending | Pending |
| #174 | Reconcile issuer active-risk live validation docs with characterization suite | Open | Live validation docs/tests | Pending | Pending |
| #173 | Clarify integration capabilities so simulation support is workflow-scoped | Open | Integration capabilities/API docs | Pending | Pending |
| #172 | Normalize upstream request fingerprint operation keys across portfolios | Open | Auditability/lineage fingerprinting | Pending | Pending |
| #171 | Bound upstream dependency operation labels in metrics, contracts, and runbooks | Open | Observability labels/contracts/docs | Pending | Pending |
| #170 | Run mesh contract validation in GitHub feature, PR, and main gates | Open | CI mesh gates | Pending | Pending |
| #169 | Align stateful risk Sharpe risk-free sourcing with declared source authority | Open | Stateful risk source authority | Pending | Pending |
| #168 | Require explicit trust-telemetry coverage for every active risk data product | Open | Trust telemetry contracts/tests | Pending | Pending |
| #167 | Complete service observability boundary behind narrow ports | Open | Observability ports/architecture | Pending | Pending |
| #166 | Fail enterprise startup when capability rules miss supported write routes | Open | Enterprise startup policy | Pending | Pending |
| #165 | Apply log-return methodology to portfolio risk metric series | Open | Risk methodology/calculation | Pending | Pending |
| #164 | Document enterprise authorization caller context in OpenAPI | Open | OpenAPI/security documentation | Pending | Pending |
| #163 | Add protected-access proof for operational diagnostics and metrics | Open | Protected operations endpoints | Pending | Pending |
| #162 | Map malformed upstream return dates to upstream invalid responses | Open | Upstream return parsing/error mapping | Pending | Pending |
| #161 | Add trusted-ingress proof for enterprise authorization headers | Open | Trusted ingress/security tests | Pending | Pending |
| #160 | Make readiness dependency status implementation-backed or narrow configured-only claims | Open | Readiness/supportability | Pending | Pending |
| #158 | Add idempotency controls for concentration simulation change application | Open | Concentration simulation idempotency | Pending | Pending |
| #157 | Handle 404 async returns-series result status before generic upstream error mapping | Open | Lotus-performance async returns polling | Pending | Pending |

## Batch Plan

1. Close hygiene and baseline truth first: #195, #193, #184, #170.
2. Close security and HTTP boundary controls: #161, #163, #164, #166, #181, #183, #185.
3. Close upstream resilience and pagination issues: #157, #162, #175, #176, #186.
4. Close calculation and concentration correctness issues: #158, #165, #169, #177, #178, #179.
5. Close API, vocabulary, trust, evidence, observability, and documentation alignment: #168, #171,
   #172, #173, #174, #187, #188, #189, #190, #191.
6. Close architecture/modularity issues alongside the relevant code slices: #167, #180, #182.

## Current Docs/Wiki/Context Decision

This matrix is repo-local review evidence. No wiki source change is required for the initial issue
matrix because no operator-facing behavior has changed yet. Wiki/source documentation will be
updated in the specific slices that change public, operator, support, or onboarding truth.
