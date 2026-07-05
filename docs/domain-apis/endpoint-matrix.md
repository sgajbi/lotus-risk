# Endpoint Matrix

This matrix is the current service-wide readiness view for `lotus-risk`.

Status meanings:

- `full`: implemented, documented, and validated to the current production standard
- `partial`: implemented for an approved subset, with an explicit remaining gap
- `operational`: non-domain endpoint; available and working

## Endpoint Readiness

| Endpoint | Category | Purpose | Supported Modes | Gold-Standard Status | Primary Upstream Inputs | Remaining Gap / Constraint |
|---|---|---|---|---|---|---|
| `GET /health` | Operational | compatibility health | operational | operational | none | none |
| `GET /health/live` | Operational | liveness | operational | operational | none | none |
| `GET /health/ready` | Operational | service readiness with configured-only dependency view | operational | operational | internal runtime state + configured-only dependency view for lotus-core and lotus-performance | Does not actively probe upstream reachability; downstream operation failures surface through endpoint errors, supportability metadata, metrics, and optional dependency status overrides |
| `GET /metadata` | Operational | service/version/rounding metadata | operational | operational | internal constants | none |
| `GET /metrics` | Operational | Prometheus metrics | operational | operational | internal metrics registry | none |
| `GET /ops` | Operational | consolidated operational diagnostics | operational | operational | runtime readiness + canonical dependency configuration and optional override status for lotus-core and lotus-performance | Dependency rows are configured-only by default, not live reachability probes |
| `GET /integration/capabilities` | Integration | capability/workflow publication | integration metadata | full | internal typed constants and support metadata | query shaping by consumer/tenant is still intentionally absent |
| `POST /analytics/risk/calculate` | Domain analytics | portfolio risk metrics | `stateless`, `stateful` | full | stateful return sourcing via lotus-performance; source-backed risk-free returns from lotus-core via returns-series when Sharpe is requested | simulation is intentionally unsupported |
| `POST /analytics/risk/drawdown` | Domain analytics | realized drawdown analytics | `stateless`, `stateful` | full | stateful return sourcing via lotus-performance | simulation is intentionally unsupported |
| `POST /analytics/risk/rolling-metrics` | Domain analytics | rolling historical risk diagnostics | `stateless`, `stateful` | full | lotus-performance for portfolio/benchmark returns; lotus-core for risk-free series and reporting-currency resolution | simulation is intentionally unsupported; broader enterprise archetype coverage still requires additional seeded live portfolios beyond the canonical baseline |
| `POST /analytics/risk/historical-attribution` | Domain analytics | historical risk and active-risk attribution decomposition | `stateless`, `stateful` | partial | stateless caller-supplied returns/exposures; stateful sourcing uses lotus-performance for portfolio/benchmark returns and benchmark exposure context, and lotus-core for portfolio exposure history and instrument enrichment | stateful `ACTIVE_RISK` supports `POSITION`, `SECTOR`, `ASSET_CLASS`, and `ISSUER`; simulation is intentionally unsupported |
| `POST /analytics/risk/concentration` | Domain analytics | concentration analytics and HHI metrics | `stateless`, `stateful`, `simulation` | full | lotus-core snapshot and simulation session contracts | non-empty simulation changes require `Idempotency-Key`; lotus-core owns replay/conflict enforcement for the propagated key and change-set fingerprint |
| `POST /analytics/risk/mandate-health-context` | Domain analytics | source-owned mandate risk health context derived from tracking-error methodology | `stateless` | partial | caller-supplied portfolio and benchmark return observations | bounded first-wave context only; does not create mandate actions, rebalance waves, client communication, or execution |
| `POST /analytics/risk/regime-scenario-pack/evaluate` | Domain analytics | governed CIO regime scenario-pack evaluation with optional per-security contribution evidence | `stateless` | full | caller-supplied exposure weights, optional reconciled exposure components, and risk-owned scenario-pack definitions | does not forecast market states, perform full repricing, or accept browser-owned scenario methodology |
| `POST /analytics/risk/risk-event-cohorts/evaluate` | Domain analytics | source-owned affected-cohort membership for governed risk events | `stateless` | partial | caller-supplied candidate portfolios, exposure weights, and risk-owned event definitions | does not create rebalance waves, approvals, campaign workflow, or client communications |

## Mode Support Detail

| Endpoint | Stateless | Stateful | Simulation |
|---|---|---|---|
| `POST /analytics/risk/calculate` | full | full | unsupported by contract |
| `POST /analytics/risk/drawdown` | full | full | unsupported by contract |
| `POST /analytics/risk/rolling-metrics` | full | full | unsupported by contract |
| `POST /analytics/risk/historical-attribution` | full | partial | unsupported by contract |
| `POST /analytics/risk/concentration` | full | full | full |
| `POST /analytics/risk/mandate-health-context` | partial | unsupported by contract | unsupported by contract |
| `POST /analytics/risk/regime-scenario-pack/evaluate` | full | unsupported by contract | unsupported by contract |
| `POST /analytics/risk/risk-event-cohorts/evaluate` | partial | unsupported by contract | unsupported by contract |

## Highest-Value Remaining Gap

The previously material functional gap inside the approved API surface is now implemented:

- stateful `ACTIVE_RISK` historical attribution with `grouping_dimension=ISSUER`

Current handling is intentional and explicit:

- request validation accepts issuer active-risk requests and rejects only `CUSTOM` stateful grouping
- `/integration/capabilities` marks issuer active-risk as supported through workflow notes
- response metadata publishes an empty `stateful_active_risk_gated_grouping_dimensions` list
- live characterization should prove `POSITION`, `SECTOR`, `ASSET_CLASS`, and `ISSUER` stateful active-risk against governed upstreams before broader portfolio-archetype claims

## Live Validation Breadth

The default live validation baseline covers canonical portfolio `PB_SG_GLOBAL_BAL_001`, which is a
global balanced private-banking portfolio.

For `POST /analytics/risk/rolling-metrics`, the canonical live baseline now includes successful
stateful `ROLLING_SHARPE` validation against populated lotus-core USD risk-free coverage for
`2026-01-01` through `2026-03-31`, alongside the adjacent stateful rolling volatility, beta,
tracking error, information ratio, and max drawdown paths.

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
historical attribution reconciliation fields, issuer active-risk support metadata, concentration-only
simulation support, and audit metadata. These rules are part of the risk contract because otherwise
correct calculations can become misleading at the product surface.

See `docs/domain-apis/risk-product-surface-alignment.md`.

## Related Detail Docs

- [integration-capabilities.md](./integration-capabilities.md)
- [risk-calculate.md](./risk-calculate.md)
- [risk-drawdown.md](./risk-drawdown.md)
- [risk-rolling-metrics.md](./risk-rolling-metrics.md)
- [risk-historical-attribution.md](./risk-historical-attribution.md)
- [risk-concentration.md](./risk-concentration.md)
- [risk-mandate-health-context.md](./risk-mandate-health-context.md)
- [regime-scenario-pack-evaluation.md](./regime-scenario-pack-evaluation.md)
- [risk-product-surface-alignment.md](./risk-product-surface-alignment.md)
