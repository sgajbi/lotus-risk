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
  - normal: `status: "ready"`
  - draining: HTTP `503`, `status: "draining"`
- Alignment:
  - aligned with platform readiness requirement.

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

## Operational Alignment Verdict

- Current state: compliant on health/metadata/metrics/ops.
