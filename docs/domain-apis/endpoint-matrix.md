# Endpoint Matrix

| Endpoint | Category | Purpose | Modes Supported Now | Target Modes | Primary Upstream Inputs | Primary Downstream Consumers | Availability |
|---|---|---|---|---|---|---|---|
| `GET /health` | Operational | compatibility health | operational | operational | none | platform stack probes, ops tooling | exists |
| `GET /health/live` | Operational | liveness | operational | operational | none | orchestrator/container probes | exists |
| `GET /health/ready` | Operational | readiness | operational | operational | internal runtime state | orchestrator/container probes | exists |
| `GET /metadata` | Operational | service/version/rounding metadata | operational | operational | internal constants | tooling/ops/clients | exists |
| `GET /metrics` | Operational | Prometheus metrics | operational | operational | internal metrics registry | observability stack | exists |
| `GET /ops` | Operational | consolidated operational diagnostics | operational | operational | runtime readiness + config internals | ops/platform automation | exists |
| `GET /integration/capabilities` | Integration | capability/workflow publication | integration metadata | integration metadata | internal typed constants | lotus-gateway capability aggregator | exists (context-aware query shaping needs enhancement) |
| `POST /analytics/risk/calculate` | Domain analytics | portfolio risk metrics | stateless + stateful | stateless + stateful + simulation | stateful return sourcing via lotus-performance (`/integration/returns/series`, `core_api_ref`); simulation still pending | lotus-report, external/advanced integrations, future gateway flows | partial (simulation pending) |
| `POST /analytics/risk/drawdown` | Domain analytics | realized drawdown analytics | stateless + stateful | stateless + stateful + simulation | stateful return sourcing via lotus-performance (`/integration/returns/series`, `core_api_ref`); simulation still pending | lotus-report, lotus-gateway, PB/WM advisory channels | partial (simulation pending) |
| `POST /analytics/risk/concentration` | Domain analytics | concentration HHI metrics | stateless + stateful + simulation | stateless + stateful + simulation | stateful/simulation sourcing via lotus-core snapshot and simulation session contracts | direct consumers + migrated gateway path | exists |
| `POST /analytics/workbench/risk-proxy` | Legacy compatibility | removed endpoint | none | none | none | none | removed |
