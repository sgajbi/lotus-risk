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
5. one remaining functional gap inside the approved analytics surface is stateful `ACTIVE_RISK + ISSUER`.

## Downstream Preservation Rules

Gateway, Workbench, reporting, and AI consumers must preserve:

1. signed VaR semantics,
2. attribution `total_value`, `reconciled_sum`, `residual`, and contributor fields,
3. issuer active-risk gating,
4. concentration-only simulation support,
5. lineage and upstream request-fingerprint metadata.

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
4. preserve audit and lineage metadata whenever responses are stored or passed onward,
5. do not rewrite signed VaR into an always-positive loss figure unless the presentation layer explicitly records that sign-convention conversion.

## Integration Sources

- `docs/domain-apis/endpoint-matrix.md`
- `docs/domain-apis/integration-capabilities.md`
- `docs/domain-apis/risk-product-surface-alignment.md`
- `docs/domain-apis/RFC-0082-upstream-contract-family-map.md`

## Read Next

1. use [Security and Governance](./Security-and-Governance.md) for the contract-discipline view,
2. use [Operations Runbook](./Operations-Runbook.md) when stateful integration failures may be upstream/runtime issues,
3. use [Troubleshooting](./Troubleshooting.md) when downstream behavior does not match declared capability support.
