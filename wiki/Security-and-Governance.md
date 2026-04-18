# Security and Governance

## Governance Posture

For `lotus-risk`, governance is mainly about analytical truth, contract discipline, and clear
upstream authority boundaries.

The important rules are:

1. do not broaden workflow support beyond what the contract declares,
2. do not hide supportability gaps behind generic UI wording,
3. do not let downstream consumers silently change risk meaning,
4. keep upstream authority lines explicit between `lotus-risk`, `lotus-core`, and `lotus-performance`.

## Core Contract Rules

The highest-value rules for this repo are:

1. signed VaR and expected shortfall semantics must be preserved,
2. attribution reconciliation fields must stay attached to contributor outputs,
3. stateful issuer active-risk must remain visibly gated,
4. simulation must remain concentration-only,
5. lineage and upstream request-fingerprint metadata must survive downstream shaping.

## API Governance

`lotus-risk` is under strong contract governance:

1. no-alias rules are enforced,
2. OpenAPI quality is enforced,
3. API vocabulary validation is enforced,
4. test-pyramid discipline is enforced,
5. security audit and Docker build are part of the real CI contract.

## Upstream Boundary Discipline

`lotus-risk` must not absorb authority that belongs elsewhere.

Keep these lines clear:

1. `lotus-performance` owns performance returns and benchmark exposure context,
2. `lotus-core` owns snapshot, enrichment, simulation, and reference contracts,
3. `lotus-risk` owns the risk analytics semantics and outputs built from those inputs.

## Supportability Truth

A feature being implemented is not the same as a feature being broadly supportable.

Current examples:

1. historical attribution exists, but one important stateful active-risk path is still intentionally partial,
2. live validation exists, but enterprise archetype breadth is still limited,
3. concentration simulation is real, but simulation support does not generalize to the rest of the service.

## Source Documents

- `docs/domain-apis/risk-product-surface-alignment.md`
- `docs/domain-apis/endpoint-matrix.md`
- `docs/standards/risk-analytics-contract.md`
- `docs/standards/platform-compliance-assessment.md`

## Read Next

1. use [Integrations](./Integrations.md) for the downstream contract view,
2. use [RFC Index](./RFC-Index.md) for the local decision trail,
3. use [Roadmap](./Roadmap.md) for the remaining supportability gaps.
