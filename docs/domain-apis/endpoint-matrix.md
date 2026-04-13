# Endpoint Matrix

This matrix is the current service-wide readiness view for `lotus-risk`.

Status meanings:

- `full`: implemented, documented, and validated to the current production standard
- `partial`: implemented for an approved subset, with an explicit remaining gap
- `operational`: non-domain endpoint; available and working
- `removed`: intentionally absent from the runtime surface

## Endpoint Readiness

| Endpoint | Category | Purpose | Supported Modes | Gold-Standard Status | Primary Upstream Inputs | Remaining Gap / Constraint |
|---|---|---|---|---|---|---|
| `GET /health` | Operational | compatibility health | operational | operational | none | none |
| `GET /health/live` | Operational | liveness | operational | operational | none | none |
| `GET /health/ready` | Operational | dependency-aware readiness | operational | operational | internal runtime state + dependency runtime view for lotus-core and lotus-performance | none |
| `GET /metadata` | Operational | service/version/rounding metadata | operational | operational | internal constants | none |
| `GET /metrics` | Operational | Prometheus metrics | operational | operational | internal metrics registry | none |
| `GET /ops` | Operational | consolidated operational diagnostics | operational | operational | runtime readiness + canonical dependency configuration/runtime status for lotus-core and lotus-performance | none |
| `GET /integration/capabilities` | Integration | capability/workflow publication | integration metadata | full | internal typed constants and support metadata | query shaping by consumer/tenant is still intentionally absent |
| `POST /analytics/risk/calculate` | Domain analytics | portfolio risk metrics | `stateless`, `stateful` | full | stateful return sourcing via lotus-performance | simulation is intentionally unsupported |
| `POST /analytics/risk/drawdown` | Domain analytics | realized drawdown analytics | `stateless`, `stateful` | full | stateful return sourcing via lotus-performance | simulation is intentionally unsupported |
| `POST /analytics/risk/rolling-metrics` | Domain analytics | rolling historical risk diagnostics | `stateless`, `stateful` | full | lotus-performance for portfolio/benchmark returns; lotus-core for risk-free series and reporting-currency resolution | simulation is intentionally unsupported; rolling Sharpe remains data-dependent on live lotus-core risk-free coverage for unvalidated currencies/windows |
| `POST /analytics/risk/historical-attribution` | Domain analytics | historical risk and active-risk attribution decomposition | `stateless`, `stateful` | partial | stateless caller-supplied returns/exposures; stateful sourcing uses lotus-performance for portfolio/benchmark returns and benchmark exposure context, and lotus-core for portfolio exposure history and instrument enrichment | stateful `ACTIVE_RISK` supports `POSITION`, `SECTOR`, and `ASSET_CLASS`; `ISSUER` remains gated by benchmark issuer exposure semantics; simulation is intentionally unsupported |
| `POST /analytics/risk/concentration` | Domain analytics | concentration analytics and HHI metrics | `stateless`, `stateful`, `simulation` | full | lotus-core snapshot and simulation session contracts | none |
| `POST /analytics/workbench/risk-proxy` | Legacy compatibility | removed endpoint | none | removed | none | intentionally removed from runtime and OpenAPI |

## Mode Support Detail

| Endpoint | Stateless | Stateful | Simulation |
|---|---|---|---|
| `POST /analytics/risk/calculate` | full | full | unsupported by contract |
| `POST /analytics/risk/drawdown` | full | full | unsupported by contract |
| `POST /analytics/risk/rolling-metrics` | full | full | unsupported by contract |
| `POST /analytics/risk/historical-attribution` | full | partial | unsupported by contract |
| `POST /analytics/risk/concentration` | full | full | full |

## Highest-Value Remaining Gap

The only remaining material functional gap inside the approved API surface is:

- stateful `ACTIVE_RISK` historical attribution with `grouping_dimension=ISSUER`

Current handling is intentional and explicit:

- request validation rejects unsupported stateful issuer requests with HTTP `422`
- `/integration/capabilities` marks historical attribution as `partial`
- OpenAPI and domain docs describe the gate
- live characterization proves:
  - supported stateful `SECTOR` active-risk works
  - upstream benchmark exposure context rejects `ISSUER`

## Live Validation Breadth

The default live validation baseline covers canonical portfolio `PB_SG_GLOBAL_BAL_001`, which is a
global balanced private-banking portfolio.

Enterprise portfolio-archetype coverage is governed by
`docs/operations/live-risk-validation-matrix.md`. Additional archetypes must have real seeded
portfolio IDs and endpoint-specific evidence before they are counted as validated.

## Audit Lineage

All analytics endpoint metadata now includes `lineage_version`, `request_fingerprint`,
`source_services`, and `upstream_request_fingerprints`. Endpoint-specific metadata remains
responsible for methodology version, observation counts, alignment policy, and coverage diagnostics.

See `docs/domain-apis/risk-audit-lineage.md`.

## Observability

Risk analytics endpoint execution metrics are labeled by endpoint, input mode, and outcome.
Direct upstream dependency metrics are labeled by dependency, operation, outcome, and deterministic
failure category.

See `docs/domain-apis/risk-observability.md`.

## Product-Surface Alignment

Downstream gateway, Workbench, reporting, and AI consumers must preserve signed VaR semantics,
historical attribution reconciliation fields, issuer active-risk gating, concentration-only
simulation support, and audit metadata. These rules are part of the risk contract because otherwise
correct calculations can become misleading at the product surface.

See `docs/domain-apis/risk-product-surface-alignment.md`.

## Related Detail Docs

- [integration-capabilities.md](C:\Users\Sandeep\projects\lotus-risk\docs\domain-apis\integration-capabilities.md)
- [risk-calculate.md](C:\Users\Sandeep\projects\lotus-risk\docs\domain-apis\risk-calculate.md)
- [risk-drawdown.md](C:\Users\Sandeep\projects\lotus-risk\docs\domain-apis\risk-drawdown.md)
- [risk-rolling-metrics.md](C:\Users\Sandeep\projects\lotus-risk\docs\domain-apis\risk-rolling-metrics.md)
- [risk-historical-attribution.md](C:\Users\Sandeep\projects\lotus-risk\docs\domain-apis\risk-historical-attribution.md)
- [risk-concentration.md](C:\Users\Sandeep\projects\lotus-risk\docs\domain-apis\risk-concentration.md)
- [risk-product-surface-alignment.md](C:\Users\Sandeep\projects\lotus-risk\docs\domain-apis\risk-product-surface-alignment.md)
