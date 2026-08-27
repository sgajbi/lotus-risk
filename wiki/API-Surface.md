# API Surface

Every operation `lotus-risk` publishes, taken from the generated OpenAPI document on `main`. There
are **17**: eight risk analytics operations and nine operational.

## Risk analytics

All eight are `POST` — a risk calculation takes a body of returns, exposures and options, not a
query string.

| operation | answers |
|---|---|
| `POST /analytics/risk/calculate` | the core risk metrics for a portfolio over a window |
| `POST /analytics/risk/drawdown` | realized drawdown analytics |
| `POST /analytics/risk/rolling-metrics` | the same metrics as a rolling series rather than a point |
| `POST /analytics/risk/historical-attribution` | which exposures drove a metric, over history |
| `POST /analytics/risk/concentration` | concentration analytics, with simulation support |
| `POST /analytics/risk/mandate-health-context` | mandate risk-health context for a portfolio |
| `POST /analytics/risk/regime-scenario-pack/evaluate` | governed regime scenario-pack evaluation |
| `POST /analytics/risk/risk-event-cohorts/evaluate` | which portfolios a risk event affects |

## Operational

| operation | purpose |
|---|---|
| `GET /health` | service health |
| `GET /health/live` | process liveness |
| `GET /health/ready` | readiness, including upstream posture |
| `GET /metadata` | service, policy, build and provenance metadata |
| `GET /version` | the same provenance, standalone |
| `GET /ops` | operational diagnostics |
| `GET /ops/trust-telemetry` | trust and lineage telemetry |
| `GET /integration/capabilities` | **the support contract** — see below |
| `GET /metrics` | Prometheus exposition |

`/metadata` and `/version` expose identical service, policy, build, image and CI provenance: commit
SHA, branch or ref, build timestamp, repository URL, image digest and CI pipeline run id. The image
digest arrives from registry or deployment metadata via `LOTUS_IMAGE_DIGEST`; a local unpublished
build reports an explicit unavailable value rather than a plausible-looking one.

## Capabilities are the contract, not a successful response

`GET /integration/capabilities` publishes the **implementation support contract**: which workflows
exist, their supported input modes, and their support status. It is built from a static workflow
specification, so it is the same document in every deployment — it does not inspect runtime
configuration, readiness, or whether upstreams are reachable.

That makes it authoritative for one question and silent on another:

| question | ask | caveat |
|---|---|---|
| is this workflow supported by the implementation at all? | `GET /integration/capabilities` | static; identical in every deployment |
| is this deployment configured for its upstreams? | `GET /health/ready`, `GET /ops` | **configured-only** — see below |
| did *this* call actually get a usable answer? | the supportability block on the response | the only surface derived from a real attempt |

`/health/ready` and `/ops` resolve dependency views from configuration plus optional status
overrides; **neither performs a live probe.** A configured but unreachable `lotus-core` or
`lotus-performance` still reports `ready` unless an override says otherwise. Treat them as
configuration diagnostics, not reachability checks.

That leaves the response's own supportability block as the only surface derived from an actual
attempt — which is why reason codes such as `stale_source_observations` and `benchmark_unavailable`
matter more here than a green readiness probe.

The operating rule for downstream teams, stated in [Home](Home#current-posture) and repeated
here because it is the one most often broken:

> Use `/integration/capabilities` and the endpoint matrix as the support contract. **Do not infer
> workflow support from one successful endpoint response.**

An endpoint returning `200` proves that one request shape was serviceable. It does not prove the
workflow behind it is supported for your portfolio, your metric, or your mode. Equally, a capability
entry does not prove the deployment can serve it today — and readiness will not tell you either.
Read the supportability block on the response.

## The metric vocabulary

Eight metrics are accepted by name. The set is closed — a request naming anything else is rejected
rather than silently ignored:

`VOLATILITY` · `DRAWDOWN` · `SHARPE` · `SORTINO` · `BETA` · `TRACKING_ERROR` ·
`INFORMATION_RATIO` · `VAR`

Historical attribution accepts a narrower set — `VOLATILITY` and `TRACKING_ERROR` — and mandate
health context reports on `TRACKING_ERROR` only. Each metric's definition, inputs and conventions
are authored per metric under
[`docs/methodologies/metrics/`](https://github.com/sgajbi/lotus-risk/tree/main/docs/methodologies/metrics);
that directory is the authority for *how* a number is produced, and this page only says which names
the API accepts.

Three metrics depend on benchmark inputs — **`BETA`, `TRACKING_ERROR` and `INFORMATION_RATIO`**.
`VAR` does not: it is computed from the portfolio series alone.

**The two surfaces handle a missing benchmark differently, and the difference is the HTTP contract:**

| surface | behaviour without benchmark data |
|---|---|
| `POST /analytics/risk/calculate` | the request is **valid**. `benchmark_returns` defaults to empty; the affected metrics carry a deterministic error payload in their `details`, and the `degraded` / `benchmark_unavailable` posture is emitted **once, response-level**, in `metadata.calculation_supportability` |
| `POST /analytics/risk/historical-attribution` | requesting `ACTIVE_RISK` or `TRACKING_ERROR` attribution without benchmark returns (stateless) or benchmark exposure history (exposure-driven) is a **validation failure** |

A client calling `calculate` must therefore read two different places, and neither is a status
code: `metadata.calculation_supportability` for the response-level posture, and each metric's
`details` for what went wrong with that metric. A `RiskValue` carries only `value` and `details` —
there is no per-metric supportability field to read. Neither surface computes a benchmark-dependent
metric from portfolio data alone and reports it as though it were sound.

## Supportability vocabularies

A response carries not just a number but whether that number should be relied on. **There are three
vocabularies, not one** — branching on the wrong set is how a consumer rejects a valid state.

### Risk calculation family

Applies to `calculate`, `drawdown`, `rolling-metrics`, `historical-attribution` and
`concentration`. Three closed dimensions:

| dimension | values |
|---|---|
| state | `ready`, `stale`, `degraded`, `empty`, `error`, `permission_blocked`, `unsupported` |
| reason | `calculation_complete`, `benchmark_unavailable`, `calculation_quality_issue`, `insufficient_aligned_observations`, `insufficient_observations`, `no_return_observations`, `permission_blocked`, `stale_source_observations`, `unsupported_input_mode` |
| freshness | `current`, `same_day`, `stale`, `unknown` |

The distinction that most often matters is `insufficient_observations` versus
`insufficient_aligned_observations`: the first means there was not enough history, the second means
portfolio and benchmark history did not overlap enough — a different fix, and a different
conversation with the data owner. `empty` and `error` differ too: `empty` means the calculation ran
and had nothing to work on; `error` means it could not run.

### Scenario pack

`regime-scenario-pack/evaluate` uses a governance-shaped set, and **does not carry the
reason/freshness pair above**:

| state | emitted when |
|---|---|
| `ready` | evaluated with no breach and no governance obstacle |
| `pending_review` | an otherwise-ready evaluation detected a breach, or pack applicability is pending |
| `degraded` | evaluated with reduced confidence |
| `blocked` | CIO approval is not confirmed, or the pack is not applicable to the portfolio |

Severity ordering used when aggregating is `ready` < `pending_review` < `degraded` < `blocked` —
note that `degraded` outranks `pending_review`.

### Risk-event cohorts

`risk-event-cohorts/evaluate` uses the same state *type* but different semantics. Reading it as a
governance state is the mistake to avoid:

| state | emitted when | reason code |
|---|---|---|
| `ready` | at least one affected portfolio was identified | `RISK_EVENT_AFFECTED_COHORT_READY` |
| `degraded` | some candidate exposure buckets were unsupported | `RISK_EVENT_PARTIAL_UNSUPPORTED_EXPOSURE_BUCKETS` |
| `pending_review` | **no portfolio met the impact threshold** — an empty cohort | `RISK_EVENT_NO_AFFECTED_PORTFOLIOS` |

`pending_review` here is not an approval step and this endpoint creates no approvals. Treat it as
"nothing was affected, have a look at whether that is expected", and handle it as an empty result
rather than routing it into a review workflow. `blocked` is declared by the type but is not emitted
by the cohort engine.

### Mandate health

`mandate-health-context` uses a third set:

`ready` · `attention` · `unavailable`

`attention` is a business signal — the mandate warrants a look — not a service degradation.

Because all three sets are closed, each can be branched on mechanically. Branch on the set belonging
to the endpoint you called.

## Request bounds and ingress

Write requests are bounded by `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES`, with
`ENTERPRISE_INGRESS_MAX_BODY_BYTES` and `ENTERPRISE_ASGI_MAX_BODY_BYTES` required at enterprise
startup to prove the effective external limits exist and are no larger than the in-process limit.

The trusted-ingress marker (`X-Lotus-Trusted-Ingress`) gates write requests and the protected
operational paths `/ops`, `/ops/trust-telemetry` and `/metrics` — **but only when
`ENTERPRISE_TRUSTED_INGRESS_SECRET` is configured.** With the secret unset, as in default and local
deployments, `trusted_ingress_authorized` permits the request and no marker is needed. Enterprise
bank mode is what makes the marker mandatory, by requiring the secret. Health probes never need it.
See
[Security and Governance](Security-and-Governance) and
[`docs/configuration.md`](https://github.com/sgajbi/lotus-risk/blob/main/docs/configuration.md).

## Current limits

Documented so that a `200` is not read as broader support than exists:

1. simulation is supported only for **concentration**
2. stateful `ACTIVE_RISK` attribution supports the `POSITION`, `SECTOR`, `ASSET_CLASS` and
   `ISSUER` grouping dimensions; **`CUSTOM` is rejected** on the stateful path. The `ISSUER`
   dimension draws on `lotus-performance` benchmark exposure context issuer groups.
   Simulation is not supported for attribution.
3. live validation defaults to the canonical portfolio `PB_SG_GLOBAL_BAL_001`
4. broader enterprise claims need more seeded archetypes and evidence

## Read next

1. [Overview](Overview) — what the service owns
2. [Architecture](Architecture) — stateless and stateful execution paths
3. [Integrations](Integrations) — upstream dependencies and consumer expectations
4. [Glossary](Glossary) — the risk vocabulary
