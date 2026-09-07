# What each file in `quality/` is

Fourteen files live here and they are not one category. This page is the classification, and
`tests/unit/test_quality_artifact_classification.py` holds it to the code: it fails if a file here is
unclassified, if the generator writes something classified authored, or if an authored file has no
reader.

Nothing here is removed on the basis of its extension, its directory, or the artifact count.

## Authored records — written by a person, reproducible from nothing

Committed unambiguously. `scripts/generate_quality_baseline.py` must never write one, and the test
above enforces that by parsing the generator's write targets rather than trusting this list.

| File | Read by |
| --- | --- |
| `agent_effectiveness_review.md` | `tests/unit/test_agent_effectiveness_review.py` |
| `branch_protection_policy.v1.json` | `scripts/check_branch_protection_policy.py` — compares live protection against it |
| `final_pr_body.md` | `tests/unit/test_final_pr_readiness_evidence.py` |
| `final_pr_readiness.md` | `tests/unit/test_final_pr_readiness_evidence.py` |
| `final_refactor_closure_audit.md` | `tests/unit/test_final_pr_readiness_evidence.py` |
| `openapi_artifact_evidence.md` | `tests/unit/test_final_pr_readiness_evidence.py` |
| `refactor_decisions.md` | `tests/unit/test_quality_baseline_evidence.py` |
| `security_findings.md` | `tests/unit/test_quality_baseline_evidence.py` |

**`final_pr_readiness.md` and `openapi_artifact_evidence.md` are authored**, though issue #279's
original table listed them as generated. They are named in prose *inside* generated reports, which is
what made them look produced; nothing writes them. Acting on that table would have swept two authored
files that a test depends on. The issue warned that `architecture_rules.md` and
`api_governance_rules.md` "read like authored standards and are `write_text` targets" — this is that
trap in the mirror, and the issue fell into it.

## Generated measurements — overwritten wholesale on each run

Written by `scripts/generate_quality_baseline.py`. Six files, not the eight #279 listed.

| File |
| --- |
| `api_governance_rules.md` |
| `architecture_rules.md` |
| `baseline_report.md` |
| `ci_quality_gates.md` |
| `quality_scorecard.md` |
| `refactor_health_report.md` |

## Retained baselines — none

No file here is currently a baseline that a later run is compared against. The six generated files
are regenerated wholesale and compared to nothing; the eight authored ones are read for content, not
for comparison. Recorded as an empty category on purpose, because "retained baseline" is the label
that makes a stale number look deliberate.

## Known defect: these measurements can be arbitrarily stale, and are

`.github/workflows/quality-baseline.yml` is named **Report Only** and behaves that way: it
regenerates `quality/` on every PR, uploads it as an artifact, and compares nothing. The committed
files can therefore describe a tree that no longer exists, and the lane is green either way.

Measured 2026-09-08:

- `quality/baseline_report.md` on `main` records **`635 passed`**. The suite is **1052**.
- Regenerating on an unchanged tree rewrites four of the six files.

**A `--check` gate is the obvious remedy and does not work yet.** `baseline_report.md` embeds raw
`pytest` stdout — progress dots, per-run timings and test ordering — so two runs on an identical tree
differ. A byte-comparison check would fail on a tree nobody touched, which is a gate that cannot pass
rather than one that cannot fail.

Making staleness fail therefore requires separating the report's deterministic content from its
embedded transcript first. That is #279's remaining work and is tracked there rather than half-done
here.
