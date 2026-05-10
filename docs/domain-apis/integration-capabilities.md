# Integration Capabilities Endpoint Assessment

## Endpoint

- `GET /integration/capabilities`

## Purpose

- Publish `lotus-risk` capability/workflow contract for cross-service orchestration (notably `lotus-gateway` platform capability aggregation).

## Current Execution Modes

- Stateless: not applicable (metadata endpoint).
- Stateful: not applicable.
- Simulation: not applicable.

## Current Required Inputs

- none.

## Input Source and Availability

| Input | Source App | Availability | Notes |
|---|---|---|---|
| capability feature/workflow definitions | lotus-risk internal constants/contracts | Exists | typed constants and response model implemented. |

## Current Output Contract

- `source_service: "lotus-risk"`
- `policy_version: "risk.v1"`
- `supported_input_modes: ["stateless", "stateful", "simulation"]`
- `features`:
  - `risk.analytics.risk_analytics`
  - `risk.analytics.drawdown`
  - `risk.analytics.concentration`
  - `risk.analytics.rolling_metrics`
  - `risk.analytics.historical_attribution`
  - `risk.analytics.regime_scenario_pack`
  - `risk.analytics.risk_event_affected_cohort`
  - `risk.analytics.metrics`
  - `risk.observability.calculation_supportability`
- `workflows`:
  - `risk_snapshot`
  - `drawdown_analytics`
  - `concentration_risk`
  - `rolling_risk_analytics`
  - `historical_risk_attribution`
  - `regime_scenario_pack_evaluation`
  - `risk_event_affected_cohort`

Each workflow now also publishes:

- `endpoint_path`
- `supported_input_modes`
- `support_status`
- `notes`

This allows consumers to discover that:

- concentration supports simulation
- risk/calculate, drawdown, rolling, and historical attribution do not
- historical attribution remains `partial` because stateful active-risk `ISSUER` is gated
- historical-attribution response metadata is the authoritative active-risk support contract
- risk snapshot VaR and expected shortfall are signed return-threshold metrics
- historical attribution residual and `reconciled_sum` must be preserved with contributors
- regime scenario-pack evaluation is a stateless source-owned workflow that returns worst-case loss,
  policy-threshold breach posture, lineage, and bounded reason codes from risk-owned CIO scenario
  definitions
- risk-event affected-cohort evaluation is a stateless source-owned workflow that returns affected
  portfolio membership, exclusions, source refs, impact scores, supportability posture, and bounded
  reason codes from risk-owned event definitions
- downstream product surfaces must derive simulation and issuer active-risk affordances from this
  payload, not from broad service-level support for the word `simulation`
- downstream consumers must also treat
  `metadata.stateful_active_risk_supported_grouping_dimensions`,
  `metadata.stateful_active_risk_gated_grouping_dimensions`, and
  `metadata.stateful_active_risk_gate_reason` as authoritative when historical attribution is used

## Upstream/Downstream Dependency Notes

- Downstream consumers:
  - `lotus-gateway` capability aggregation (`/api/v1/platform/capabilities`).
  - `lotus-manage` future RFC41-WTBD-003 wave trigger consumption for risk-event cohorts.
  - downstream cleanup for undeclared risk capability query params is tracked in
    `sgajbi/lotus-gateway#113`.
- Upstream dependencies:
  - none at runtime (static contract payload today).

## Alignment Assessment

- Strengths:
  - typed contract exists and is integration-tested.
  - vocabulary is centralized in constants to reduce drift.
  - workflow-level mode support is explicit enough for gateway and Workbench surfaces to avoid
    unsupported simulation and issuer active-risk affordances.
  - risk calculation supportability is implementation-backed across `risk/calculate`, drawdown,
    rolling metrics, historical attribution, and concentration through
    `metadata.calculation_supportability` and `lotus_risk_calculation_supportability_total`, so
    downstream consumers can distinguish ready, stale, degraded, and empty risk results without
    inspecting sensitive request context.
- Gaps:
  - endpoint remains globally published and does not expose consumer- or tenant-shaped query controls.
  - some downstream callers still send advisory query params for cross-service parity; that drift should
    be fixed downstream rather than modeled here because lotus-risk enforces no-alias contract governance.
  - policy diagnostics richness is minimal compared to gateway-normalized expectations.

## Decisions Required

1. Should risk capability responses remain globally published until a real consumer-specific rule exists, or should a future shaped contract be introduced with canonical snake_case parameters?
2. Should risk capability responses include richer policy diagnostics metadata (version provenance, strict mode) consistent with broader policy-governed contract patterns?
