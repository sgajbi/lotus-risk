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

- none (query params are not currently required by this service for capability shaping).

## Input Source and Availability

| Input | Source App | Availability | Notes |
|---|---|---|---|
| `consumerSystem` query context (optional for policy shaping) | caller (`lotus-gateway` or peer service) | Needs enhancement | currently ignored/not modeled in lotus-risk endpoint signature. |
| `tenantId` query context (optional for policy shaping) | caller (`lotus-gateway` or peer service) | Needs enhancement | currently ignored/not modeled in lotus-risk endpoint signature. |
| capability feature/workflow definitions | lotus-risk internal constants/contracts | Exists | typed constants and response model implemented. |

## Current Output Contract

- `sourceService: "lotus-risk"`
- `policyVersion: "risk.v1"`
- `supportedInputModes: ["stateless", "stateful", "simulation"]`
- `features`:
  - `risk.analytics.risk_analytics`
  - `risk.analytics.drawdown`
  - `risk.analytics.concentration`
  - `risk.analytics.rolling_metrics`
  - `risk.analytics.metrics`
- `workflows`:
  - `risk_snapshot`
  - `drawdown_analytics`
  - `concentration_risk`
  - `rolling_risk_analytics`
  - `historical_risk_attribution`

Each workflow now also publishes:

- `endpoint_path`
- `supported_input_modes`
- `support_status`
- `notes`

This allows consumers to discover that:

- concentration supports simulation
- risk/calculate, drawdown, rolling, and historical attribution do not
- historical attribution remains `partial` because stateful active-risk `ISSUER` is gated

## Upstream/Downstream Dependency Notes

- Downstream consumers:
  - `lotus-gateway` capability aggregation (`/api/v1/platform/capabilities`).
- Upstream dependencies:
  - none at runtime (static contract payload today).

## Alignment Assessment

- Strengths:
  - typed contract exists and is integration-tested.
  - vocabulary is centralized in constants to reduce drift.
- Gaps:
  - endpoint does not currently accept/reflect `consumerSystem` and `tenantId` query context as many peer services do.
  - policy diagnostics richness is minimal compared to gateway-normalized expectations.

## Decisions Required

1. Should `lotus-risk /integration/capabilities` accept `consumerSystem` and `tenantId` for parity with other Lotus services?
2. Should risk capability responses include richer policy diagnostics metadata (version provenance, strict mode) consistent with broader policy-governed contract patterns?
