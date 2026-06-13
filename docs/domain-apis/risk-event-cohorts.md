# Risk Event Affected Cohorts

## Endpoint

`POST /analytics/risk/risk-event-cohorts/evaluate`

## Business Purpose

This endpoint evaluates candidate portfolios against governed risk-event definitions and returns a
source-owned affected cohort. It is intended for downstream consumers that need risk-owned evidence
for event-driven monitoring or future manage-wave trigger inputs.

## Current Support

| Item | Status |
| --- | --- |
| Input mode | `stateless` only |
| Support status | partial first-wave product |
| Product declaration | `RiskEventAffectedCohort:v1` |
| Runtime owner | `lotus-risk` |
| Primary tests | `tests/unit/test_risk_event_cohort_engine.py`, `tests/unit/test_risk_event_cohort_api.py` |

## Inputs

The caller supplies:

1. a governed `risk_event_id`,
2. candidate portfolios,
3. source-owned exposure weights for each candidate,
4. optional threshold and source-reference context as modeled by `src/app/contracts/risk_event_cohort_inputs.py`.

The service evaluates those inputs against risk-owned event definitions in
`src/app/services/risk_event_cohort_engine.py`.

## Outputs

The response returns:

1. affected portfolio membership,
2. excluded portfolios and exclusion reasons,
3. source-owned impact scores,
4. lineage source refs,
5. supportability posture,
6. bounded reason codes.

## Explicit Non-Ownership

This endpoint does not create:

1. rebalance waves,
2. approvals,
3. campaign workflows,
4. client communications,
5. orders or execution.

Downstream consumers must preserve source refs, impact scores, supportability, and lineage metadata
when using the response as evidence.

## Where To Look Next

1. Service-wide posture: `docs/domain-apis/endpoint-matrix.md`.
2. Capability publication: `docs/domain-apis/integration-capabilities.md`.
3. Consumer preservation rules: `docs/domain-apis/risk-product-surface-alignment.md`.

