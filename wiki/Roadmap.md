# Roadmap

## Current Phase

`lotus-risk` is beyond the foundation phase. The service already has a strong, real analytics
surface and explicit CI/governance posture.

The remaining roadmap work is mostly about:

1. closing known supportability gaps,
2. expanding live-evidence breadth,
3. keeping downstream contract usage truthful.

## What Is Already Real

The current runtime and contract already provide:

1. full risk/calculate support for stateless and stateful modes,
2. full drawdown support for stateless and stateful modes,
3. full rolling-metrics support for stateless and stateful modes,
4. full concentration support for stateless, stateful, and simulation modes,
5. partial historical attribution support with explicit gating,
6. typed capability publication through `/integration/capabilities`,
7. readiness and ops diagnostics tied to real dependency posture.

## What Remains Intentionally Bounded

Important current limits:

1. broaden live portfolio-archetype validation for stateful `ACTIVE_RISK + ISSUER`,
2. simulation remains concentration-only,
3. enterprise live-validation breadth remains limited to the canonical portfolio baseline unless more seeded archetypes are registered with evidence,
4. downstream consumers still need more cross-repo proof that they preserve the risk contract correctly.

## Near-Term Focus

The next meaningful work is:

1. broadening live validation across more seeded archetypes,
2. tightening consumer-side preservation of risk semantics,
3. keeping upstream family boundaries explicit under RFC-0082,
4. closing any remaining supportability gaps without weakening contract discipline.

## Evidence Expansion Priority

The current live validation matrix still needs real seeded coverage for archetypes such as:

1. `equity_heavy`
2. `fixed_income_heavy`
3. `cash_heavy`
4. `multi_currency`
5. `short_history`
6. `sparse_benchmark`
7. `high_concentration`

That work matters more than decorative documentation claims because it changes what the repo can
truthfully say about enterprise readiness.

## Source Documents

- `docs/rfcs/README.md`
- `docs/rfcs/RFC-0008-enterprise-bank-readiness-and-live-risk-validation-baseline.md`
- `docs/operations/live-risk-validation-matrix.md`
- `docs/domain-apis/endpoint-matrix.md`

## Read Next

1. use [RFC Index](./RFC-Index.md) for the local decision inventory,
2. use [Integrations](./Integrations.md) to see how roadmap gaps affect downstream consumers,
3. use [Security and Governance](./Security-and-Governance.md) for why these limits stay explicit.
