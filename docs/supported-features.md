# Lotus Risk Supported Features

This page separates current implementation-backed support from bounded, planned, and backlog
posture. Treat `/integration/capabilities` and `docs/domain-apis/endpoint-matrix.md` as the
runtime-facing support contract.

## Implementation-Backed Risk Products

1. `RiskMetricsReport:v1`
2. `RollingRiskMetricsReport:v1`
3. `DrawdownAnalyticsReport:v1`
4. `ConcentrationRiskReport:v1`
5. `RegimeScenarioPackEvaluation:v1`
6. `RiskEventAffectedCohort:v1`
7. `MandateRiskHealthContext:v1`

## Current Support Matrix

| Product or workflow | Endpoint | Current support | Important limits |
| --- | --- | --- | --- |
| `RiskMetricsReport:v1` | `POST /analytics/risk/calculate` | full for stateless and stateful modes | simulation is intentionally unsupported |
| `DrawdownAnalyticsReport:v1` | `POST /analytics/risk/drawdown` | full for stateless and stateful modes | simulation is intentionally unsupported |
| `RollingRiskMetricsReport:v1` | `POST /analytics/risk/rolling-metrics` | full for stateless and stateful modes | broader portfolio-archetype proof remains limited to the live validation matrix |
| `ConcentrationRiskReport:v1` | `POST /analytics/risk/concentration` | full for stateless, stateful, and simulation modes | simulation support must not be generalized to other risk workflows; non-empty simulation changes require `Idempotency-Key` for lotus-core replay/conflict enforcement |
| Historical attribution | `POST /analytics/risk/historical-attribution` | partial | stateful `ACTIVE_RISK` supports `POSITION`, `SECTOR`, `ASSET_CLASS`, and `ISSUER`; `CUSTOM` grouping and simulation remain unsupported |
| `RegimeScenarioPackEvaluation:v1` | `POST /analytics/risk/regime-scenario-pack/evaluate` | full for stateless source-owned scenario-pack evaluation | does not forecast markets, perform full repricing, or accept UI-owned scenario methodology |
| `RiskEventAffectedCohort:v1` | `POST /analytics/risk/risk-event-cohorts/evaluate` | partial stateless first-wave product | does not create rebalance waves, approvals, campaign workflows, or client communications |
| `MandateRiskHealthContext:v1` | `POST /analytics/risk/mandate-health-context` | partial stateless first-wave product | does not create mandate actions, rebalance waves, orders, execution, or client communications |
| Capability publication | `GET /integration/capabilities` | implemented | global capability publication only; executable mode affordances are authoritative at `workflows[].supported_input_modes`, while top-level `supported_input_modes` is only an aggregate inventory; no tenant- or consumer-shaped query controls |
| Operations | `/health`, `/health/live`, `/health/ready`, `/metadata`, `/version`, `/ops`, `/ops/trust-telemetry`, `/metrics` | implemented | `/metadata` and `/version` expose the same build/image/CI provenance metadata; `/ops`, `/ops/trust-telemetry`, and `/metrics` require trusted-ingress proof in enterprise mode; `/ops/trust-telemetry` is repo-owned raw telemetry seed material, not platform-certified trust posture |

## Current Evidence Boundary

Supported features are bounded by the repository engineering context, domain API documentation,
methodology documents, and repo-native tests. Broader enterprise-bank approval still requires the
seeded portfolio archetype evidence described in `docs/operations/live-risk-validation-matrix.md`.

## Planned Or Backlog

1. Broader seeded live portfolio archetype coverage for enterprise-bank claims.
2. Consumer-side proof that gateway, Workbench, reporting, and AI surfaces preserve signed VaR,
   attribution reconciliation, concentration-only simulation, supportability, and lineage semantics.
3. RFC-0009 Enterprise Risk Intelligence Operating Layer slices. These remain planned until each
   slice is implemented, tested, documented, and validated.
