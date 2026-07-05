# Risk Observability

`lotus-risk` exposes Prometheus metrics at `GET /metrics`.

## Endpoint Execution Metrics

| Metric | Labels | Meaning |
| --- | --- | --- |
| `lotus_risk_endpoint_executions_total` | `endpoint`, `input_mode`, `outcome` | Count of risk analytics endpoint executions after service-operation and response-contract validation. |
| `lotus_risk_endpoint_execution_seconds` | `endpoint`, `input_mode`, `outcome` | Duration histogram for risk analytics endpoint executions after service-operation and response-contract validation. |

The governed endpoint label values are:

1. `risk/calculate`,
2. `drawdown`,
3. `rolling-metrics`,
4. `historical-attribution`,
5. `concentration`,
6. `mandate-risk-health-context`,
7. `regime-scenario-pack`,
8. `risk-event-cohort`,
9. `unknown`.

Tracked input modes are the request contract modes `stateless`, `stateful`, and `simulation`
where supported by the workflow. `unknown` is reserved for defensive fallback classification.
Outcomes are `success` and `failure`. A failure includes exceptions raised by the analytics
operation and invalid responses that fail the declared FastAPI response model before the service
records endpoint success.

## Upstream Dependency Metrics

| Metric | Labels | Meaning |
| --- | --- | --- |
| `lotus_risk_upstream_requests_total` | `dependency`, `operation`, `outcome`, `category` | Count of direct upstream requests from `lotus-risk`. |
| `lotus_risk_upstream_request_seconds` | `dependency`, `operation`, `outcome`, `category` | Duration histogram for direct upstream requests. |

Governed dependencies are `lotus-core` and `lotus-performance`. Governed upstream operation values
are:

1. `/simulation-sessions`,
2. `/simulation-sessions/{session_id}/changes`,
3. `/integration/portfolios/{portfolio_id}/core-snapshot`,
4. `/integration/instruments/enrichment-bulk`,
5. `/integration/portfolios/{portfolio_id}/analytics/position-timeseries`,
6. `/integration/reference/risk-free-series`,
7. `/integration/reference/risk-free-series/coverage`,
8. `/integration/returns/series`,
9. `/integration/returns/series/status/{calculation_id}`,
10. `/integration/returns/series/results/{calculation_id}`,
11. `/integration/benchmarks/exposure-context`,
12. `unknown`.

`category="ok"` means the upstream call returned a usable response. Failure categories are derived
from deterministic upstream error classification:

1. `timeout`,
2. `transport`,
3. `upstream_failure`,
4. `rejected_request`,
5. `data_gap`,
6. `invalid_response`,
7. `throttled`.

Outcomes are `success` and `failure`.

## Calculation Supportability Metrics

| Metric | Labels | Meaning |
| --- | --- | --- |
| `lotus_risk_calculation_supportability_total` | `operation`, `supportability_state`, `reason`, `freshness_bucket` | Count of risk calculation supportability outcomes using the same bounded posture emitted in `metadata.calculation_supportability.metric_labels`. |
| `lotus_analytics_freshness_bucket_total` | `service`, `operation`, `freshness_bucket`, `supportability_state` | RFC-0108 cross-service backend freshness counter emitted from the same source-owned supportability posture. |

The governed supportability and freshness operation values are `risk/calculate`, `drawdown`,
`rolling-metrics`, `historical-attribution`, `concentration`, `mandate-risk-health-context`,
`regime-scenario-pack`, `risk-event-cohort`, and `unknown`. The freshness metric uses
`service="lotus-risk"`.

The supported states are `ready`, `stale`, `degraded`, `empty`, `error`, `permission_blocked`, and
`unsupported`. Freshness buckets are `current`, `same_day`, `stale`, and `unknown`. The labels are
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
9. `unsupported_input_mode`,
10. `unknown`.

## HTTP Request Metrics

| Metric | Labels | Meaning |
| --- | --- | --- |
| `http_requests_total` | `handler`, `method`, `status` | Count of HTTP requests by route handler, method, and status class. |

Governed handler values are:

1. `/ops`,
2. `/ops/trust-telemetry`,
3. `/health`,
4. `/health/live`,
5. `/health/ready`,
6. `/metadata`,
7. `/metrics`,
8. `/analytics/risk/calculate`,
9. `/analytics/risk/drawdown`,
10. `/analytics/risk/rolling-metrics`,
11. `/analytics/risk/historical-attribution`,
12. `/analytics/risk/concentration`,
13. `/analytics/risk/mandate-health-context`,
14. `/analytics/risk/regime-scenario-pack/evaluate`,
15. `/analytics/risk/risk-event-cohorts/evaluate`.

Governed methods are `GET`, `POST`, `PUT`, `DELETE`, and `OPTIONS`. Governed status classes are
`1xx`, `2xx`, `3xx`, `4xx`, and `5xx`.

The HTTP 5xx alert is `lotus-risk-http-5xx`; use
`docs/runbooks/service-operations.md#http-5xx-alert` for triage. Endpoint, upstream dependency, and
calculation supportability alerts route to
`docs/runbooks/service-operations.md#endpoint-failure-rate-alert`,
`docs/runbooks/service-operations.md#upstream-dependency-failure-alert`, and
`docs/runbooks/service-operations.md#calculation-supportability-alert`.

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
