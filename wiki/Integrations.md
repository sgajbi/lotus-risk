# Integrations

## Current Scope and Evidence

This page describes the implemented Lotus Risk integration contracts and their fail-closed
dependency behavior. Supported claims are anchored in the source routes, their OpenAPI contract,
and the focused integration tests; availability of an upstream route is not evidence that its
economic inputs are complete.

| Reader | Use this page to decide | Evidence and next action |
| --- | --- | --- |
| Product and demo | Which Risk workflows preserve upstream truth | Start with [Primary Executable Contracts](#primary-executable-contracts) and the published capability contract. |
| Operations and support | How to classify an upstream failure | Use [Upstream Dependency Failure Alert](#upstream-dependency-failure-alert); escalate only with the bounded operation and error category. |
| Engineering | Ownership, tenant scope, and contract expectations | Review [Upstream Contract Families](#upstream-contract-families) and the linked domain API documents before changing a client. |

## Integration Model

`lotus-risk` is primarily consumed through `lotus-gateway`, but the domain contract itself is owned
here.

The key rule is:

1. `lotus-risk` owns risk meaning,
2. `lotus-gateway` owns experience composition,
3. downstream UI and reporting surfaces must preserve the semantics they receive.

## Primary Executable Contracts

The main executable risk workflows are:

1. `POST /analytics/risk/calculate`
2. `POST /analytics/risk/drawdown`
3. `POST /analytics/risk/rolling-metrics`
4. `POST /analytics/risk/historical-attribution`
5. `POST /analytics/risk/concentration`
6. `POST /analytics/risk/mandate-health-context`
7. `POST /analytics/risk/regime-scenario-pack/evaluate`
8. `POST /analytics/risk/risk-event-cohorts/evaluate`

The main discovery contract is:

1. `GET /integration/capabilities`

## Capability Publication Rule

Downstream consumers must derive workflow support from `/integration/capabilities`, not from broad
service-level assumptions.

This matters because:

1. concentration supports simulation,
2. the other risk workflows do not,
3. historical attribution is intentionally `partial`,
4. workflow notes carry real supportability meaning,
5. regime scenario-pack evaluation is stateless and source-owned by `lotus-risk`,
6. per-security regime scenario contribution rows are available when callers supply reconciled
   exposure components,
7. risk-event affected-cohort evaluation and mandate risk health context are stateless first-wave
   products,
8. stateful `ACTIVE_RISK + ISSUER` is supported through lotus-performance benchmark exposure context issuer groups,
9. only explicit gross/currency stateful `ACTIVE_RISK + TRACKING_ERROR` for `SECTOR`/`ASSET_CLASS` can consume Performance v1 group-return evidence as empirical; other active sets remain labelled proxies, and live joined replay/correction acceptance is pending under [Risk #283](https://github.com/sgajbi/lotus-risk/issues/283).

## Downstream Preservation Rules

Gateway, Workbench, reporting, and AI consumers must preserve:

1. signed VaR semantics,
2. attribution `total_value`, `reconciled_sum`, `residual`, and contributor fields,
   together with `metadata.metric_unit_semantics` -- the values are unreadable without their stated units,
3. issuer active-risk support metadata,
4. concentration-only simulation support,
5. regime scenario-pack evaluation reason codes and threshold-breach posture,
6. regime scenario-pack per-security contribution rows when present,
7. risk-event affected-cohort source refs and impact scores,
8. mandate risk health threshold posture and non-claim reason codes,
9. lineage and upstream request-fingerprint metadata,
10. stateful drawdown `source_returns_evidence`, including its calculation identity, source
    freshness, and reconciled coverage. A Risk request fingerprint is not a substitute for this
    producer response evidence.

If those are dropped or flattened, a numerically correct response can still become product-wrong.

## Upstream Contract Families

Stateful workflows depend on governed upstream inputs:

1. `lotus-performance` for returns and benchmark exposure context,
2. `lotus-core` for snapshots, simulation contracts, enrichment, and risk-free reference data.

For stateful active-risk attribution, `lotus-risk` accepts benchmark exposure rows only when
Performance declares `metadata.exposure_source_quality.status` as `complete` with zero omissions.
An incomplete declaration maps to a bounded upstream data gap; missing or contradictory quality
metadata maps to an invalid upstream response. It never renormalizes or calculates from a partial
benchmark exposure subset. See the [historical attribution upstream contract](https://github.com/sgajbi/lotus-risk/blob/main/docs/domain-apis/lotus-core-performance-requirements-for-historical-attribution.md).
Risk also binds each exposure page to the admitted portfolio/date/window/frequency/currency request
and refuses malformed or out-of-scope rows, pagination, duplicate row identities, or changed
benchmark identity as an invalid upstream response. It never silently drops a row from a
producer-declared complete set. The current offset page token is not a durable source snapshot;
live replay/correction stability remains a separate producer acceptance question.

Admitted tenant authority (`X-Tenant-Id`) travels with every **tenant-owned** upstream request —
returns-series submit and its async status/result polls, benchmark exposure context, core
snapshots, position analytics timeseries, and simulation session create/changes. Instrument
enrichment and risk-free series/coverage remain globally scoped reference data with no tenant
owner. Core enterprise admission still requires the admitted caller header for risk-free
series/coverage, forwarded per request without a tenant body filter; this does not turn the
reference facts into tenant-owned data. Core snapshots also require the admitted tenant in the
JSON body, identical to the header;
snapshots and position timeseries declare `consumer_system=lotus-risk` instead of inheriting a
Performance default. A conflicting internal scope refuses before I/O. The discriminator is
recorded at the transports and every client port.

Stateful Risk Sharpe and rolling Sharpe share one currency rule: an explicit caller
`reporting_currency` is used as supplied; otherwise a tenant-admitted Core baseline snapshot
selects portfolio/reporting currency before Performance returns and Core risk-free requests. The
Performance returns response is not a currency authority. A missing Core currency is an invalid
upstream response, and the Core snapshot request is retained in lineage.

Use:

- `docs/domain-apis/RFC-0082-upstream-contract-family-map.md`

## Practical Integration Guidance

Use `lotus-risk` directly or through gateway with these rules:

1. preserve input-mode truth,
2. do not offer unsupported workflow modes,
3. treat partial historical attribution support as a real product limit,
   including declared group-return unavailability; the BUSINESS portfolio-return calendar
   excludes validated in-period weekend contribution points from covariance without treating
   missing weekdays as holidays or zero returns,
4. consume regime scenario-pack evaluation as source-owned stress evidence rather than
   reconstructing scenario shocks downstream,
5. preserve regime scenario-pack contribution rows in proof packs and product surfaces when
   `exposure_components` were supplied,
6. preserve audit and lineage metadata whenever responses are stored or passed onward,
7. for stateful drawdown, treat stale or incomplete source evidence as the published
   supportability state; do not relabel a calculable subset as current or complete,
8. do not rewrite signed VaR into an always-positive loss figure unless the presentation layer explicitly records that sign-convention conversion.

## Integration Sources

- `docs/domain-apis/endpoint-matrix.md`
- `docs/domain-apis/integration-capabilities.md`
- `docs/domain-apis/risk-product-surface-alignment.md`
- `docs/domain-apis/RFC-0082-upstream-contract-family-map.md`

## Read Next

1. use [Security and Governance](Security-and-Governance) for the contract-discipline view,
2. use [Operations Runbook](Operations-Runbook) when stateful integration failures may be upstream/runtime issues,
3. use [Troubleshooting](Troubleshooting) when downstream behavior does not match declared capability support.
