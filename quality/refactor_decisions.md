# Lotus Risk Refactor Decisions

## REF-DEC-001: Preserve The Initial Baseline By Commit Identity

The immutable enterprise-refactor baseline is commit `3254774`. Generated
`quality/baseline_report.md` represents current state and must identify its branch, commit, and
working-tree posture. This prevents routine regeneration from silently rewriting the "before"
evidence.

## REF-DEC-002: Continue Incrementally From Current Main

The earlier refactor series is already merged into `main`. This continuation will not recreate or
rewrite that history. New work will target remaining measurable gaps with small, reviewable commits.

## REF-DEC-003: Do Not Invent A Layer Before A Real Boundary Exists

Current routers, services, contracts, dependencies, and integrations already provide useful
boundaries. A separate application/domain/ports package will be introduced only where it removes
concrete coupling and can be enforced with architecture tests.

