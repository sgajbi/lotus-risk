# Risk Upstream Failure Behavior

`lotus-risk` depends on `lotus-core` and `lotus-performance` for stateful analytics. This document defines the deterministic failure behavior expected by RFC-0008 Slice 1.

## Dependency Ownership

| Dependency | Used For |
| --- | --- |
| `lotus-core` | portfolio snapshots, simulation sessions, instrument enrichment, position analytics history, risk-free series |
| `lotus-performance` | portfolio returns, benchmark returns, benchmark exposure context |

## Error Classification

| Upstream Condition | Lotus HTTP Status | Lotus Error Code | Retryable | Category |
| --- | --- | --- | --- | --- |
| Invalid upstream payload | `502` | `UPSTREAM_INVALID_RESPONSE` | `false` | `invalid_response` |
| Missing required upstream data | `424` | `FAILED_DEPENDENCY` | `false` | `data_gap` |
| Upstream `400`, `404`, or `422` | `424` | `FAILED_DEPENDENCY` | `false` | `rejected_request` |
| Upstream `429` | `503` | `UPSTREAM_THROTTLED` | `true` | `throttled` |
| Upstream `5xx` | `502` | `UPSTREAM_FAILURE` | `true` | `upstream_failure` |
| Timeout | `504` | `UPSTREAM_TIMEOUT` | `true` | `timeout` |
| Transport/network failure | `503` | `UPSTREAM_UNAVAILABLE` | `true` | `transport` |

## Response Detail Contract

Every upstream failure returned by `lotus-risk` should include deterministic details:

1. `service`: upstream dependency name,
2. `operation`: upstream operation path,
3. `category`: stable failure class,
4. `retryable`: boolean retry guidance,
5. `upstream_status_code`: present for HTTP upstream failures.

Client-facing messages expose only a bounded failure class such as `Upstream dependency failed.`
or `Upstream dependency returned an invalid response.` Dependency identity, operation path,
category, retryability, and upstream HTTP status are carried in structured `details` fields. Raw
upstream response bodies, downstream exception text, stack traces, credentials, and tokens are
never included in the client-facing `message` or problem-details `detail` fields.

`lotus-performance` async returns-series result polling has one operation-specific exception to the
generic HTTP classification table: `404` from the accepted `result_path` is treated as a pending
result while the upstream async execution is still materializing. Unexpected result statuses, such
as `400` or `5xx`, continue to use the standard upstream HTTP classification.

Upstream failures use the standard Lotus error envelope and additive RFC 7807/problem-details
compatibility fields inside the `error` object. `error.code` remains the stable Lotus machine code;
`error.type`, `error.title`, `error.status`, `error.detail`, and `error.instance` are provided for
clients and gateways that normalize problem-details payloads.

## Correlation IDs

When a caller sends `X-Correlation-Id`, `lotus-risk` forwards it to upstream clients and includes the same correlation ID in the error envelope returned to the caller.

## Operator Guidance

1. `invalid_response` means the dependency contract shape did not match what `lotus-risk` can safely consume.
2. `data_gap` means the dependency is reachable, but the requested data is absent or insufficient.
3. `rejected_request` usually means the stateful request cannot be fulfilled for the provided identifiers or unsupported upstream semantics.
4. `throttled`, `upstream_failure`, `timeout`, and `transport` are retryable classes, but clients should use bounded retry policies.
5. `/health/ready` and `/ops` expose dependency state for readiness and operational diagnosis; endpoint-level failures still carry richer operation-specific context.

## Upstream Client Resilience Posture

The following explicit downstream transport posture is defined in
`src/app/integrations/_downstream_client_profile.py` and used by both adapters:

- `lotus-core` resolves `LOTUS_CORE_TIMEOUT_SECONDS`, `LOTUS_CORE_MAX_CONNECTIONS`,
  `LOTUS_CORE_MAX_KEEPALIVE_CONNECTIONS`, and `LOTUS_CORE_KEEPALIVE_EXPIRY_SECONDS`.
- `lotus-performance` resolves `LOTUS_PERFORMANCE_TIMEOUT_SECONDS`,
  `LOTUS_PERFORMANCE_MAX_CONNECTIONS`, `LOTUS_PERFORMANCE_MAX_KEEPALIVE_CONNECTIONS`,
  and `LOTUS_PERFORMANCE_KEEPALIVE_EXPIRY_SECONDS`.
- `lotus-performance` also controls async polling through
  `LOTUS_PERFORMANCE_ASYNC_POLL_INTERVAL_SECONDS` and
  `LOTUS_PERFORMANCE_ASYNC_MAX_POLLS`.
- Local development falls back to defaults for malformed downstream profile overrides, while
  enterprise runtime enforcement rejects explicit invalid timeout, pool, keepalive, and async
  polling overrides with bounded `invalid_downstream_runtime_setting:<ENV_NAME>` startup issue
  codes.
- FastAPI lifespan startup creates one reusable HTTP connection pool per upstream dependency.
  Lifespan shutdown marks the service draining, closes both owned pools, and preserves any
  explicitly injected client used by tests or controlled runtimes.
- Directly constructed adapters remain usable outside the FastAPI lifespan and create a bounded
  temporary client for each operation.
- Timeout and retry-class handling remains deterministic:
  transport errors map to `UPSTREAM_TIMEOUT` or `UPSTREAM_UNAVAILABLE`,
  while HTTP `429` and `5xx` map to retryable throttling and upstream-failure classes.
- Shared stateful return parsing maps malformed upstream return dates to
  `UPSTREAM_INVALID_RESPONSE` before request-level validation handlers can classify the failure as
  caller input.

## Validation Evidence

The failure classification matrix is covered by `tests/unit/test_upstream_errors.py` and client-specific coverage in:

1. `tests/unit/test_lotus_core_client.py`,
2. `tests/unit/test_lotus_performance_client.py`,
3. `tests/unit/test_app_lifecycle.py`,
4. `tests/unit/test_main_error_handlers.py`.
