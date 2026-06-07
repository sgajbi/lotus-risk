# Troubleshooting

## Service Is Up but Stateful Endpoints Fail

Symptoms:

1. `/health/live` is healthy,
2. `/health/ready` is degraded or non-ready,
3. stateful risk workflows fail while stateless ones work.

Check:

1. `/health/ready`
2. `/ops`
3. `LOTUS_PERFORMANCE_BASE_URL`
4. `LOTUS_CORE_BASE_URL`

This is often an upstream configuration or reachability problem, not a risk-engine bug.

## Wrong Upstream URL Causes Misleading 404s

Symptoms:

1. stateful flows fail with unexpected `404`,
2. returns-series or benchmark-context fetches look missing,
3. direct analytics code seems fine.

Most common cause:

1. `LOTUS_PERFORMANCE_BASE_URL` points at a `lotus-core` port.

Use the canonical local URL runbook before changing more code.

Malformed URLs, unsupported schemes, credential-bearing URLs, and URLs with query strings or
fragments fail during service construction. The validation error names the setting but deliberately
does not echo its value.

## Historical Attribution Looks Incomplete

Symptoms:

1. stateful historical attribution works for some dimensions but not others,
2. issuer active-risk appears missing, degraded, or rejected.

Interpretation:

1. verify the request is not using unsupported `CUSTOM` stateful grouping,
2. check `/integration/capabilities`,
3. check the endpoint matrix and product-surface alignment docs.

This is not necessarily a bug.

## Downstream Surface Looks Misleading

Symptoms:

1. VaR is shown as an always-positive loss,
2. attribution contributors are shown without residuals,
3. simulation appears available for non-concentration workflows.

This is usually a downstream contract-preservation issue, not a `lotus-risk` calculation issue.

Check:

1. `/integration/capabilities`
2. `docs/domain-apis/risk-product-surface-alignment.md`
3. the consumer-side mapping or view-model layer

## A Local Gate Fails but the Code Change Looks Small

In `lotus-risk`, small changes can still trigger large governance gates.

Check which category failed:

1. no-alias governance,
2. OpenAPI quality,
3. API vocabulary validation,
4. test-pyramid gate,
5. security audit,
6. coverage or Docker build.

In this repo, those failures often mean the change weakened a contract boundary rather than just a
style rule.

## Read Next

1. use [Validation and CI](./Validation-and-CI.md) for the gate meanings,
2. use [Operations Runbook](./Operations-Runbook.md) for runtime and upstream checks,
3. use [Integrations](./Integrations.md) when the failure is really a downstream contract issue.
