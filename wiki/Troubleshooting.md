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

## Risk Calculations Fail Because Core Timeseries Are Missing

Symptoms: a stateful risk request fails with a dependency error, and the portfolio and date
range look correct.

`portfolio_timeseries` is a `lotus-core` **source data product**. Core's
`portfolio_derived_state_service` materializes it, and also owns position-level
`position_timeseries`. **Do not escalate against `timeseries-generator-service`** — that runtime
no longer exists in Core, and older Risk guidance named it. Escalate against the product and let
Core route it; Core owns its own topology and has consolidated these services once already.

Three causes escalate differently, so establish which one applies **against Core**:

1. the portfolio is unknown to Core — not a data gap;
2. the portfolio is known but has no timeseries for the requested range — a materialization gap;
3. timeseries exist but are stale relative to the requested as-of date — a freshness gap.

**Risk will not tell you which.** An absent or empty upstream series raises a dependency failure
before any `metadata.calculation_supportability` is produced, and an upstream 4xx surfaces the
generic `rejected_request` category. The finer reasons — `insufficient_observations`,
`insufficient_aligned_observations`, `benchmark_unavailable`, `calculation_quality_issue`,
`stale_source_observations` — describe a series that exists but is insufficient, which is a
different situation. `source_product_unavailable` belongs to the separate source-observation
path, not to risk calculation supportability. Risk's response tells you the dependency failed, not why.

Missing data here is a Core-side gap, not a Risk fault, and Risk must not infer a value for it.

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

1. use [Validation and CI](Validation-and-CI) for the gate meanings,
2. use [Operations Runbook](Operations-Runbook) for runtime and upstream checks,
3. use [Integrations](Integrations) when the failure is really a downstream contract issue.
