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

| question | ask |
|---|---|
| is this workflow supported by the implementation at all? | `GET /integration/capabilities` |
| is it usable in *this* deployment right now? | `GET /health/ready`, `GET /ops`, and the supportability block on the response itself |

The operating rule for downstream teams, stated in [Home](./Home.md#current-posture) and repeated
here because it is the one most often broken:

> Use `/integration/capabilities` and the endpoint matrix as the support contract. **Do not infer
> workflow support from one successful endpoint response.**

An endpoint returning `200` proves that one request shape was serviceable. It does not prove the
workflow behind it is supported for your portfolio, your metric, or your mode. Equally, a capability
entry does not prove the deployment can serve it today — for that, read readiness and the response's
own supportability state.

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

Three metrics require benchmark inputs — **`BETA`, `TRACKING_ERROR` and `INFORMATION_RATIO`**.
`VAR` does not: it is computed from the portfolio series alone. Likewise, requesting `ACTIVE_RISK`
or `TRACKING_ERROR` attribution requires benchmark returns on the stateless path and benchmark
exposure history on the exposure-driven path. Each requirement is enforced at validation, so a
benchmark-dependent metric cannot be computed from portfolio data alone and reported as though it
were.

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

### Scenario pack and risk-event cohorts

`regime-scenario-pack/evaluate` and `risk-event-cohorts/evaluate` use a governance-shaped set, and
**do not carry the reason/freshness pair above**:

`ready` · `degraded` · `pending_review` · `blocked`

`pending_review` and `blocked` are approval states, not data-quality states — an evaluation can be
computationally fine and still not releasable.

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

Protected operator endpoints and write requests require the trusted-ingress marker
(`X-Lotus-Trusted-Ingress`) injected by the approved gateway or ingress; health probes remain
available without it. See
[Security and Governance](./Security-and-Governance.md) and
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

1. [Overview](./Overview.md) — what the service owns
2. [Architecture](./Architecture.md) — stateless and stateful execution paths
3. [Integrations](./Integrations.md) — upstream dependencies and consumer expectations
4. [Glossary](./Glossary.md) — the risk vocabulary
