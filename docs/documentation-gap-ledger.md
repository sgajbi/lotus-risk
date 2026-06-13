# Documentation Gap Ledger

This ledger records documentation issues found during the knowledge-base refresh and the disposition
for each item. Keep it current when docs, wiki, or repo truth materially change.

| ID | Area | Finding | Disposition |
| --- | --- | --- | --- |
| RISK-DOC-001 | Command surface | `Makefile` exposed stale `live-api-validate*` targets copied from `lotus-manage` and pointing at a missing `scripts/validate_live_api.py`. | Removed from the supported command surface in this slice. Do not document live validation as a make target until a real repo-native script exists. |
| RISK-DOC-002 | Navigation | README and wiki routed to useful pages, but there was no audience-oriented docs index for agents, developers, BAs, ops/support, sales/marketing, and business/product users. | Added `docs/index.md` and linked it from README/wiki. |
| RISK-DOC-003 | Supported features | `docs/supported-features.md` listed product names but did not separate implemented, partial, planned, and backlog posture. | Expanded into an implementation-backed matrix with limits and planned/backlog boundaries. |
| RISK-DOC-004 | API docs | `docs/domain-apis/endpoint-matrix.md` used absolute Windows links and omitted the risk-event cohort row from the endpoint/mode tables. | Replaced absolute links with relative links and added risk-event affected-cohort posture. |
| RISK-DOC-005 | Wiki business/product coverage | Wiki pages were operator/developer useful but did not expose a dedicated supported-features page for non-developer readers. | Added `wiki/Supported-Features.md` and sidebar navigation. |
| RISK-DOC-006 | Operations | Runbook guidance existed but was terse for escalation, observability, and enterprise deployment failure modes. | Expanded `docs/runbooks/service-operations.md` with operator checks and escalation paths. |
| RISK-DOC-007 | Migration docs | `docs/migrations/README.md` had a Markdown link target with raw parentheses that broke automated local link sanity parsing. | URL-encoded the parentheses in the link target and reran link/path sanity successfully. |

## Open Follow-Ups

1. Add a real repo-native live validation script before restoring any `live-api-validate` make
   target.
2. Add seeded portfolio IDs and evidence for pending live-validation archetypes before broadening
   enterprise-bank claims.
3. Attach cross-repo gateway and Workbench consumer proof whenever downstream risk semantics are
   promoted.

## Validation Evidence

| Check | Result |
| --- | --- |
| Markdown local link/path sanity over `README.md`, `docs/**/*.md`, and `wiki/**/*.md` | Passed; checked 114 Markdown files |
| Focused documentation and contract tests: `python -m pytest tests/unit/test_product_surface_alignment_contract.py tests/unit/test_observability_operations_contract.py tests/unit/test_configuration_docs.py tests/unit/test_final_pr_readiness_evidence.py tests/unit/test_capabilities_contract.py tests/unit/test_risk_event_cohort_api.py tests/unit/test_mandate_health_context.py -q` | Passed; 29 tests |
| `make mesh-contract-validate` | Passed |
| `make openapi-gate` | Passed |
| `make check` | Passed; includes lint, no-alias, typecheck, OpenAPI artifact, API vocabulary, mesh contracts, source-size, and 554 unit tests |
| `../lotus-platform/automation/Sync-RepoWikis.ps1 -CheckOnly -Repository lotus-risk` before merge | Ran; reported expected publication drift for repo-authored wiki source changes: `_Sidebar.md`, `Architecture.md`, `Development-Workflow.md`, `Home.md`, `Integrations.md`, `Overview.md`, `Roadmap.md`, `Supported-Features.md`, and `Validation-and-CI.md` |
| `../lotus-platform/automation/Sync-RepoWikis.ps1 -Publish -Repository lotus-risk` after merge | Passed; published wiki commit `955d4ca` from repo source |
| `../lotus-platform/automation/Sync-RepoWikis.ps1 -CheckOnly -Repository lotus-risk` after publish | Passed; `DiffCount 0` |
