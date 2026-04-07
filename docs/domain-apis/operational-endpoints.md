# Operational Endpoints Assessment

## Endpoint: `GET /health`

- Purpose: service compatibility health check.
- Execution modes supported: operational (not stateless/stateful/simulation analytics mode).
- Required inputs:
  - none.
- Input source mapping:
  - none (service self-check only).
- Availability status:
  - implemented.
- Output:
  - `status: "ok"`
  - `service: "lotus-risk"`
- Alignment:
  - aligned with platform contract health compatibility endpoint.

## Endpoint: `GET /health/live`

- Purpose: liveness probe.
- Execution modes supported: operational.
- Required inputs:
  - none.
- Input source mapping:
  - none.
- Availability status:
  - implemented.
- Output:
  - `status: "live"`
- Alignment:
  - aligned with platform liveness requirement.

## Endpoint: `GET /health/ready`

- Purpose: readiness probe.
- Execution modes supported: operational.
- Required inputs:
  - none.
- Input source mapping:
  - none.
- Availability status:
  - implemented.
- Output:
  - normal: HTTP `200`, `status: "ready"`, plus dependency runtime states
  - degraded dependency: HTTP `200`, `status: "degraded"`
  - draining or unavailable dependency: HTTP `503`, `status: "draining"` or `status: "dependency_unavailable"`
- Alignment:
  - aligned with platform readiness requirement and now surfaces dependency-aware readiness semantics.

## Endpoint: `GET /metadata`

- Purpose: service metadata contract.
- Execution modes supported: operational.
- Required inputs:
  - none.
- Input source mapping:
  - none.
- Availability status:
  - implemented.
- Output:
  - `service`
  - `version`
  - `roundingPolicyVersion`
- Alignment:
  - aligned with template-generated lotus-platform baseline.

## Endpoint: `GET /metrics`

- Purpose: Prometheus metrics exposure.
- Execution modes supported: operational.
- Required inputs:
  - none.
- Input source mapping:
  - none.
- Availability status:
  - implemented.
- Output:
  - Prometheus text payload including service and custom risk metric counters/histograms.
- Alignment:
  - aligned with platform observability standards.

## Endpoint: `GET /ops`

- Status: implemented.
- Execution modes supported: operational.
- Required inputs:
  - none (expected).
- Input source mapping:
  - runtime configuration, health/readiness/observability internals (expected).
- Availability status:
  - available in runtime and OpenAPI.
- Output:
  - `service`
  - `version`
  - `status` (`ok`/`degraded`)
  - `checks.live`
  - `checks.ready`
  - `checks.draining`
  - `inputModes`
  - `dependencies[]` with `service`, canonical `baseUrl`, runtime `status`, and optional operator `detail`

## Error Semantics

- Domain endpoints now distinguish:
  - caller validation errors: `422 INVALID_REQUEST`
  - business-rule invalidity: `400 INVALID_INPUT`
  - upstream rejected or missing dependency data: `424 FAILED_DEPENDENCY`
  - upstream malformed or failing responses: `502 UPSTREAM_FAILURE` or `502 UPSTREAM_INVALID_RESPONSE`
  - upstream unavailability: `503 UPSTREAM_UNAVAILABLE`
  - upstream timeout: `504 UPSTREAM_TIMEOUT`

## Operational Alignment Verdict

- Current state: compliant on health/metadata/metrics/ops with dependency-aware readiness and diagnostics.
