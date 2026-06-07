# Lotus Risk Codebase Review Ledger

This ledger tracks the enterprise refactor continuation from
`feat/enterprise-risk-refactor-continuation`.

| Review ID | Scope / pattern | Status | Findings and consequence | Action / follow-up | Evidence |
| --- | --- | --- | --- | --- | --- |
| RISK-REF-001 | Quality measurement and CI truthfulness | Reviewing | The generated `baseline_report.md` described current state as the initial baseline, mixed source and test hotspots, and the quality-gate guide described already-active gates as report-only. This weakened before/after evidence credibility. | Correct generated terminology and gate posture; preserve commit `3254774` as immutable initial baseline; add generator regression tests next. | `make quality-baseline`; initial baseline verified with `git show 3254774:quality/baseline_report.md` |
| RISK-REF-002 | Architecture dependency boundaries | Planned | Existing import-linter contracts are green but do not yet model a distinct application/ports layer. | Review service-to-infrastructure imports and introduce enforceable boundaries only where they match current repository truth. | `.importlinter`; `make architecture-gate` |
| RISK-REF-003 | Service hotspot modularity | Planned | Current largest source modules are `risk/period_metrics.py`, `rolling_stateful_inputs.py`, `rolling_metric_series.py`, and concentration parsing/orchestration modules. | Review by responsibility and extract only cohesive behavior with characterization tests. | `quality/baseline_report.md`; `make complexity-gate` |
| RISK-REF-004 | Security and sensitive-data controls | Planned | Existing Bandit, dependency audit, redaction, authorization, and deployment-policy evidence is strong; negative contract coverage requires review. | Record validated gaps in `quality/security_findings.md` and add focused negative tests where material. | `make security-audit`; security test packs |
| RISK-REF-005 | OpenAPI and error governance | Planned | Operation metadata is actively gated; richer RFC 7807 compatibility remains an identified gap. | Review current client contract before changing error shape; preserve compatibility unless intentionally versioned. | `make openapi-gate`; `make openapi-artifact-gate` |

