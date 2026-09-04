# Integrations

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
8. stateful `ACTIVE_RISK + ISSUER` is supported through lotus-performance benchmark exposure context issuer groups.

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
9. lineage and upstream request-fingerprint metadata.

If those are dropped or flattened, a numerically correct response can still become product-wrong.

## Upstream Contract Families

Stateful workflows depend on governed upstream inputs:

1. `lotus-performance` for returns and benchmark exposure context,
2. `lotus-core` for snapshots, simulation contracts, enrichment, and risk-free reference data.

Use:

- `docs/domain-apis/RFC-0082-upstream-contract-family-map.md`

## Practical Integration Guidance

Use `lotus-risk` directly or through gateway with these rules:

1. preserve input-mode truth,
2. do not offer unsupported workflow modes,
3. treat partial historical attribution support as a real product limit,
4. consume regime scenario-pack evaluation as source-owned stress evidence rather than
   reconstructing scenario shocks downstream,
5. preserve regime scenario-pack contribution rows in proof packs and product surfaces when
   `exposure_components` were supplied,
6. preserve audit and lineage metadata whenever responses are stored or passed onward,
7. do not rewrite signed VaR into an always-positive loss figure unless the presentation layer explicitly records that sign-convention conversion.

## Integration Sources

- `docs/domain-apis/endpoint-matrix.md`
- `docs/domain-apis/integration-capabilities.md`
- `docs/domain-apis/risk-product-surface-alignment.md`
- `docs/domain-apis/RFC-0082-upstream-contract-family-map.md`

## Read Next

1. use [Security and Governance](Security-and-Governance) for the contract-discipline view,
2. use [Operations Runbook](Operations-Runbook) when stateful integration failures may be upstream/runtime issues,
3. use [Troubleshooting](Troubleshooting) when downstream behavior does not match declared capability support.
