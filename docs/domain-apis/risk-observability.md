# Risk Observability

`lotus-risk` exposes Prometheus metrics at `GET /metrics`.

## Endpoint Execution Metrics

| Metric | Labels | Meaning |
| --- | --- | --- |
| `lotus_risk_endpoint_executions_total` | `endpoint`, `input_mode`, `outcome` | Count of risk analytics endpoint executions. |
| `lotus_risk_endpoint_execution_seconds` | `endpoint`, `input_mode`, `outcome` | Duration histogram for risk analytics endpoint executions. |

Tracked endpoint values:

1. `risk/calculate`,
2. `drawdown`,
3. `concentration`,
4. `rolling-metrics`,
5. `historical-attribution`.

Tracked input modes are the request contract modes: `stateless`, `stateful`, and `simulation`
where supported by the endpoint.

## Upstream Dependency Metrics

| Metric | Labels | Meaning |
| --- | --- | --- |
| `lotus_risk_upstream_requests_total` | `dependency`, `operation`, `outcome`, `category` | Count of direct upstream requests from `lotus-risk`. |
| `lotus_risk_upstream_request_seconds` | `dependency`, `operation`, `outcome`, `category` | Duration histogram for direct upstream requests. |

`category="ok"` means the upstream call returned a usable response. Failure categories are derived
from deterministic upstream error classification, for example:

1. `timeout`,
2. `transport`,
3. `upstream_failure`,
4. `rejected_request`,
5. `data_gap`,
6. `invalid_response`.

## Calculation Supportability Metrics

| Metric | Labels | Meaning |
| --- | --- | --- |
| `lotus_risk_calculation_supportability_total` | `operation`, `supportability_state`, `reason`, `freshness_bucket` | Count of risk calculation supportability outcomes using the same bounded posture emitted in `metadata.calculation_supportability.metric_labels`. |
| `lotus_analytics_freshness_bucket_total` | `service`, `operation`, `freshness_bucket`, `supportability_state` | RFC-0108 cross-service backend freshness counter emitted from the same source-owned supportability posture. |

The supported states are `ready`, `stale`, `degraded`, `empty`, `error`, `permission_blocked`, and
`unsupported`. Implemented operations are `risk/calculate`, `risk/drawdown`,
`risk/rolling-metrics`, `risk/historical-attribution`, and `risk/concentration`; the labels are
bounded and intentionally exclude portfolio, client, account, position, transaction, security,
trace, correlation, request-body, and response-body identifiers.

The analytics responses include `metadata.calculation_supportability` so Gateway and Workbench can
consume source-backed supportability posture without inferring it from individual metric errors,
period errors, issuer coverage, or return-series recency. Current reason values include:

The same block includes `metric_labels`. It is the implementation-backed operator contract for
`lotus_risk_calculation_supportability_total`; identifiers, correlation or trace values, security
or transaction identifiers, and request or response payload fields are explicitly excluded from
metric labels.

1. `calculation_complete`,
2. `benchmark_unavailable`,
3. `calculation_quality_issue`,
4. `insufficient_aligned_observations`,
5. `insufficient_observations`,
6. `no_return_observations`,
7. `permission_blocked`,
8. `stale_source_observations`,
9. `unsupported_input_mode`.

## Operator Use

Use endpoint metrics to answer:

1. which endpoint and mode are receiving traffic,
2. whether failures are concentrated in stateful or simulation paths,
3. whether endpoint latency regressed after methodology or upstream changes.

Use upstream metrics to answer:

1. which dependency is slow or failing,
2. whether failures are retryable infrastructure failures or deterministic data gaps,
3. which upstream operation is responsible for degraded stateful analytics.

Use calculation supportability metrics to answer:

1. whether UI-facing risk results are ready, stale, degraded, or empty,
2. whether degradation is caused by source freshness, missing benchmarks, sparse observations, or
   calculation-quality guardrails,
3. whether a support incident affects calculations broadly without exposing sensitive identifiers in
   Prometheus labels.

Correlation IDs are still the request-level trace handle. Metrics are aggregate signals and should
be used with audit-lineage metadata and structured errors for investigation.
