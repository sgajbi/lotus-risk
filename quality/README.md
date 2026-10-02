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

## Freshness and diagnostic evidence

The six generated measurements stay committed and are checked against current source/test inputs
by `make quality-baseline-check` from the repository root. The Quality Baseline workflow runs this
as a blocking **Freshness Gate** on PRs and feature branches. A mismatch names the stale file and
shows a bounded diff. Regenerate with `make quality-baseline` before committing a changed source or
test tree; whichever PR lands second must regenerate from its rebased tree.
For a quick deterministic refresh without rerunning the diagnostic commands, run
`python scripts/generate_quality_baseline.py --skip-diagnostics` from the repository root,
then run `make quality-baseline-check`.

The earlier report embedded raw pytest progress, timings, and other runner-specific command output.
It could differ twice on an unchanged tree, so a byte check would be permanently red. A normal
generation run now writes that diagnostic transcript to ignored
`output/quality/baseline-command-transcript.md`, and CI uploads it with the quality reports. The
committed `baseline_report.md` contains deterministic measurements and a SHA-256 fingerprint of
the measured source/test content, independent of branch and rebase commit identity. The transcript
is report-only; actual Feature, PR Merge and Main gates own their acceptance verdicts.

The initial baseline at commit `3254774` remains immutable. The old committed report's `635 passed`
and the 2026-09-08 observation that four of six regenerated files drifted are historical defect
evidence, not current test results. The authored records above are not generator targets, and
there are still no retained ratchet baselines in this directory.
