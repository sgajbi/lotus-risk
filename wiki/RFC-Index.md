# RFC Index

## How to Use This Page

The local RFC set for `lotus-risk` is compact enough to group by capability area rather than by one
flat list only.

The source inventory remains:

- `docs/rfcs/README.md`

## Foundation and Migration RFCs

These RFCs established the repo and its migration posture:

1. `RFC-0002` migration parity closure,
2. `RFC-0007` final production readiness and integration hardening,
3. `RFC-0008` enterprise-bank readiness and live validation baseline.

## Enterprise Product RFCs

These RFCs define the bank-buyable product direction beyond the current RFC-0008 baseline:

1. `RFC-0009` enterprise risk intelligence operating layer.

`RFC-0009` is the implementation plan for Advisor Brief Risk Lens, Risk Watchtower, CIO Scenario
Lab, risk evidence packets, grounded AI risk commentary, Manage handoff, report/archive evidence,
model-risk governance, and data-product hardening. It is a target-state plan until the named
slices are implemented, validated, documented, and merged.

The RFC permits strategic breaking changes when that is the right product design, but requires all
affected upstream and downstream Lotus repositories to be updated in the same RFC. It does not allow
a follow-up RFC or WTBD item to carry work required for the bank-buyable product claim.

## Analytics Workflow RFCs

These RFCs govern the main risk workflows:

1. `RFC-0003` concentration API stateful and simulation integration,
2. `RFC-0004` realized drawdown analytics,
3. `RFC-0005` rolling risk metrics,
4. `RFC-0006` historical risk attribution analytics.

## Platform-Level Governing RFCs

The main platform RFCs shaping this repository are:

1. `RFC-0065` performance-to-performance-and-risk split,
2. `RFC-0067` centralized API vocabulary and OpenAPI governance,
3. `RFC-0072` CI, validation, and release governance,
4. `RFC-0073` context and guidance-system governance,
5. `RFC-0082` lotus-core upstream domain-authority hardening.

These live under:

- `../lotus-platform/rfcs/`

## Practical Rule

When working in `lotus-risk`, start with:

1. `README.md`,
2. `REPOSITORY-ENGINEERING-CONTEXT.md`,
3. the endpoint matrix,
4. the specific workflow RFC you are touching.

Do not load all RFCs unless the task is genuinely governance-heavy.

## Read Next

1. use [Roadmap](./Roadmap.md) for remaining gaps and rollout shape,
2. use [Security and Governance](./Security-and-Governance.md) for the practical contract rules,
3. use [Development Workflow](./Development-Workflow.md) when RFC work implies code and docs in the same slice.
