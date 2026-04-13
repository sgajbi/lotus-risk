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

## Operator Use

Use endpoint metrics to answer:

1. which endpoint and mode are receiving traffic,
2. whether failures are concentrated in stateful or simulation paths,
3. whether endpoint latency regressed after methodology or upstream changes.

Use upstream metrics to answer:

1. which dependency is slow or failing,
2. whether failures are retryable infrastructure failures or deterministic data gaps,
3. which upstream operation is responsible for degraded stateful analytics.

Correlation IDs are still the request-level trace handle. Metrics are aggregate signals and should
be used with audit-lineage metadata and structured errors for investigation.
