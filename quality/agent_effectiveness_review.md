# Lotus Risk Agent Effectiveness Review

This register records conscious reviews of whether the enterprise refactor should improve skills,
guidance, documentation, context, or automation for future engineers and agents.

## Review Triggers

Review after every five meaningful refactor slices and before major architecture, PR, or closure
decisions.

## 2026-06-07 Review 1

| Area | Decision | Evidence / action |
| --- | --- | --- |
| Skill routing | No change | `lotus-backend-delivery-governance` and `lotus-codebase-review-ledger` remain the smallest correct skills. A new enterprise-refactor skill would duplicate the governed instruction pack and current routing. |
| Agent guidance | Improve | Added a mandatory effectiveness-review cadence to `docs/architecture/CODEBASE-REVIEW-PLAYBOOK.md`. |
| Documentation | Improve continuously | Security, observability, architecture, wiki, quality evidence, and decisions are updated in the same slices as implementation changes. |
| Repository context | No change yet | Current repository role, commands, and integration truth remain accurate. Update `REPOSITORY-ENGINEERING-CONTEXT.md` when durable architecture, command, or supportability truth changes. |
| Automation | Review next | Current feature-lane and quality-baseline workflows are green. Review reproducible scorecard and file-size regression automation in the next CI-measurement slice. |

