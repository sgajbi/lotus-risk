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
  - normal: HTTP `200`, `status: "ready"`, plus dependency configuration states
  - degraded dependency override: HTTP `200`, `status: "degraded"`
  - draining or unavailable dependency: HTTP `503`, `status: "draining"` or `status: "dependency_unavailable"`
- Alignment:
  - aligned with platform readiness requirement. Dependency entries are configured-only by default:
    `status: "configured"` and `detail: "configured_only_no_probe"` mean the dependency base URL
    is configured and safe to display, not that the upstream was actively probed. Degraded or
    unavailable dependency states are surfaced only from explicit runtime status overrides or
    endpoint-level downstream failure handling.

## Endpoint: `GET /metadata`

- Purpose: service metadata contract, including service version, policy version, build provenance,
  image provenance, and CI provenance.
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
  - `rounding_policy_version`
  - `build.git_commit_sha`
  - `build.git_branch`
  - `build.build_timestamp`
  - `build.repo_url`
  - `build.image_digest`
  - `build.ci_pipeline_run_id`
- Alignment:
  - aligned with template-generated lotus-platform baseline and Lotus image provenance
    requirements. Local unpublished builds may report an explicit unavailable image digest until
    publish/deployment metadata supplies `LOTUS_IMAGE_DIGEST`.

## Endpoint: `GET /version`

- Purpose: service version endpoint exposing the same service, policy, build, image, and CI
  provenance metadata as `GET /metadata`.
- Execution modes supported: operational.
- Required inputs:
  - none.
- Input source mapping:
  - none.
- Availability status:
  - implemented.
- Output:
  - same response contract as `GET /metadata`.
- Alignment:
  - aligned with the OCI/runtime provenance contract used by the Docker image labels.

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
  - `input_modes`
  - `dependencies[]` with `service`, canonical `base_url`, configured-only or override `status`,
    optional operator `detail`, and optional structured metadata:
    - `category` such as `transport`, `timeout`, or `data_gap`
    - `issue_code` such as `UPSTREAM_HIGH_LATENCY` or `RISK_FREE_SERIES_EMPTY`

## Error Semantics

- Domain endpoints now distinguish:
  - caller validation errors: `422 INVALID_REQUEST`
  - business-rule invalidity: `400 INVALID_INPUT`
  - upstream rejected or missing dependency data: `424 FAILED_DEPENDENCY`
  - upstream malformed or failing responses: `502 UPSTREAM_FAILURE` or `502 UPSTREAM_INVALID_RESPONSE`
  - upstream unavailability: `503 UPSTREAM_UNAVAILABLE`
  - upstream timeout: `504 UPSTREAM_TIMEOUT`

## Operational Alignment Verdict

- Current state: compliant on health/metadata/version/metrics/ops with explicit configured-only
  dependency readiness semantics, preserving degraded/unavailable runtime override diagnostics.
