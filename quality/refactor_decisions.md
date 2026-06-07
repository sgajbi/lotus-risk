# Lotus Risk Refactor Decisions

## REF-DEC-001: Preserve The Initial Baseline By Commit Identity

The immutable enterprise-refactor baseline is commit `3254774`. Generated
`quality/baseline_report.md` represents current state and must identify its branch, commit, and
working-tree posture. This prevents routine regeneration from silently rewriting the "before"
evidence.

## REF-DEC-002: Continue Incrementally From Current Main

The earlier refactor series is already merged into `main`. This continuation will not recreate or
rewrite that history. New work will target remaining measurable gaps with small, reviewable commits.

## REF-DEC-003: Do Not Invent A Layer Before A Real Boundary Exists

Current routers, services, contracts, dependencies, and integrations already provide useful
boundaries. A separate application/domain/ports package will be introduced only where it removes
concrete coupling and can be enforced with architecture tests.

## REF-DEC-004: Calculation Services Use An Observability Port

Risk calculation services accept a narrow metric-duration observer callable. Prometheus metric
construction and registration remain in `app.observability`. Import-linter prohibits direct
`prometheus_client` imports from `app.services`, keeping calculations testable without the concrete
metrics backend while preserving runtime metric behavior.

## REF-DEC-005: Treat Correlation And Trace Headers As Untrusted Input

Inbound correlation IDs are preserved only when they use a bounded safe character set. Inbound trace
IDs and `traceparent` values are preserved only when they satisfy the supported W3C format and use a
non-zero trace ID; malformed, mismatched, or unbounded values are replaced. This intentionally
hardens response-header reflection and structured request logging without changing valid callers.

## REF-DEC-006: Client-Facing Upstream Errors Are Bounded

Upstream error envelopes preserve dependency, operation, status, category, retryability, and
correlation context, but never include raw downstream response bodies or transport exception text.
This intentionally changes unsafe error-message detail while preserving the governed error codes
and status behavior used by clients.

## REF-DEC-007: Sensitive Risk API Responses Are Non-Cacheable

All responses passing through enterprise middleware, including early authorization and payload-limit
failures, carry the active policy version and conservative `no-store`, `no-referrer`, and `nosniff`
headers. This prevents sensitive analytics or error context from being cached and keeps security
posture consistent across success and rejection paths.

## REF-DEC-008: Request Observations Are Structured And Bounded

Request middleware emits a structured `request_observation` log event rather than an interpolated
text line. The event includes bounded operational fields and deliberately excludes query strings,
headers, and request/response bodies so production support can parse events without increasing
sensitive-data exposure.

## REF-DEC-009: Prevent New Source Monoliths At 450 Lines

All current Python source modules are below 402 lines. A 450-line active regression gate leaves
reasonable room for cohesive maintenance while preventing new monolithic modules. The threshold may
be reduced only after further behavior-preserving extraction proves a lower limit is practical.

## REF-DEC-010: Own Downstream HTTP Pools For The Application Lifespan

FastAPI lifespan startup creates one reusable HTTP client for `lotus-core` and one for
`lotus-performance`, making the existing connection and keepalive limits effective across
requests. Shutdown marks the service draining and closes only the pools it owns. Directly
constructed or explicitly injected adapters retain their existing compatibility behavior.

## REF-DEC-011: Fail Fast On Unsafe Downstream Base URLs

Both upstream adapters use one shared base-URL resolver. It accepts valid HTTP(S) service URLs,
including approved path prefixes, but rejects malformed hosts or ports, embedded credentials,
query strings, fragments, whitespace, and control characters. Validation errors identify only the
setting name and policy violation so a credential-bearing value cannot be reflected.

## REF-DEC-012: Enterprise Runtime Enforcement Is Fail Closed

Local development keeps its permissive defaults. When `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true`,
application construction requires the documented in-process bank posture and fails with bounded
issue codes when it is incomplete. This closes the gap between deployment policy and executable
startup behavior without claiming enforcement of external ingress or identity-provider controls.
Authorization-enforced writes also fail closed when no well-formed capability rule matches, and
overlapping path prefixes resolve deterministically to the most specific rule.

## REF-DEC-013: Problem Details Are Additive To The Lotus Error Envelope

`lotus-risk` keeps the existing `error.code`, `error.message`, `error.correlation_id`, and
`error.details` client contract. RFC 7807/problem-details metadata is added inside the same `error`
object as `type`, `title`, `status`, `detail`, and `instance` so gateways and clients can normalize
errors without a breaking top-level response shape change.

## REF-DEC-014: Split Benchmark Period Metrics From Period Orchestration

Risk period orchestration remains exposed through `calculate_period_metrics`, but benchmark-specific
period alignment, dependency error mapping, and benchmark context construction now live in
`risk/benchmark_period_metrics.py`. This reduces the largest service hotspot without changing the
caller contract or metric semantics.

## REF-DEC-015: Split Rolling Dependency Selection From Source Resolution

Rolling stateful input resolution now delegates risk-free/benchmark requirement checks and
reporting-currency resolution to `rolling_stateful_dependency_selection.py`. The source-resolution
module remains responsible for request construction, dependency calls, parsing, and final
`ResolvedStatefulRollingInputs` assembly.
