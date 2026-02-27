# Endpoint Matrix

| Endpoint | Category | Purpose | Modes Supported Now | Target Modes | Primary Upstream Inputs | Primary Downstream Consumers | Availability |
|---|---|---|---|---|---|---|---|
| `GET /health` | Operational | compatibility health | operational | operational | none | platform stack probes, ops tooling | exists |
| `GET /health/live` | Operational | liveness | operational | operational | none | orchestrator/container probes | exists |
| `GET /health/ready` | Operational | readiness | operational | operational | internal runtime state | orchestrator/container probes | exists |
| `GET /metadata` | Operational | service/version/rounding metadata | operational | operational | internal constants | tooling/ops/clients | exists |
| `GET /metrics` | Operational | Prometheus metrics | operational | operational | internal metrics registry | observability stack | exists |
| `GET /ops` | Operational | consolidated operational diagnostics | none | operational | runtime config + health/metrics internals | ops/platform automation | needs enhancement |
| `GET /integration/capabilities` | Integration | capability/workflow publication | integration metadata | integration metadata | internal typed constants | lotus-gateway capability aggregator | exists (context-aware query shaping needs enhancement) |
| `POST /analytics/risk/calculate` | Domain analytics | portfolio risk metrics | stateless | stateless + stateful + simulation | stateless payload only (today); target upstream: lotus-core, optionally lotus-performance | lotus-report, external/advanced integrations, future gateway flows | partial (stateless only) |
| `POST /analytics/risk/concentration` | Domain analytics | concentration HHI metrics | stateless | stateless + stateful + simulation | stateless payload only (today); target upstream: lotus-core | direct consumers + migrated gateway path | partial (stateless only) |
| `POST /analytics/workbench/risk-proxy` | Legacy compatibility | workbench alias for concentration risk proxy | stateless alias | deprecate/remove | stateless payload | lotus-gateway workbench | exists (legacy) |
