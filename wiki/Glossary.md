# Glossary

The vocabulary `lotus-risk` uses. Metric *definitions* — formulas, conventions, inputs — are authored
per metric under
[`docs/methodologies/metrics/`](https://github.com/sgajbi/lotus-risk/tree/main/docs/methodologies/metrics)
and are not repeated here; this page says what each term means in the contract and where its
authority lives.

## Metrics the API accepts

| term | in one line | methodology |
|---|---|---|
| **`VOLATILITY`** | dispersion of portfolio returns | `risk-volatility.md` |
| **`DRAWDOWN`** | decline from a prior peak | `risk-drawdown.md` |
| **`SHARPE`** | excess return per unit of total risk | `risk-sharpe.md` |
| **`SORTINO`** | excess return per unit of *downside* risk | `risk-sortino.md` |
| **`BETA`** | sensitivity of portfolio returns to the benchmark | `risk-beta.md` |
| **`TRACKING_ERROR`** | dispersion of returns *relative to* the benchmark | `risk-tracking-error.md` |
| **`INFORMATION_RATIO`** | active return per unit of tracking error | `risk-information-ratio.md` |
| **`VAR`** | value at risk over the configured horizon and confidence | `risk-var.md` |

**Three of these require benchmark inputs — `BETA`, `TRACKING_ERROR` and `INFORMATION_RATIO`.**
Requesting one without benchmark returns or benchmark exposure history is a validation failure, not
a silently portfolio-only answer. `VAR` is deliberately **not** among them: it is computed from the
portfolio series alone, and treating it as benchmark-dependent would make callers reject valid
requests.

## Drawdown family

Realized drawdown analytics go beyond the single `DRAWDOWN` metric:

| term | in one line |
|---|---|
| **maximum drawdown** | the worst peak-to-trough decline in the window |
| **relative maximum drawdown** | the same, measured against the benchmark |
| **average drawdown** | the mean of every strictly underwater observation — not a mean of episode-level values, so a long episode weighs proportionally more |
| **time under water** | how long the portfolio spent below its prior peak |
| **Ulcer index** | depth *and* duration of drawdown in a single number |
| **DaR / CDaR** | drawdown at risk and conditional drawdown at risk |

Each has its own methodology document under `docs/methodologies/metrics/`.

## Concentration

| term | in one line |
|---|---|
| **HHI** | Herfindahl–Hirschman index — concentration across holdings |
| **issuer HHI** | the same, aggregated to issuer rather than instrument |
| **top position weight** | the largest single position as a share of the portfolio |
| **top issuer weight** | the largest single issuer exposure |
| **top-N cumulative weight** | the combined weight of the largest N positions |
| **simulation** | a what-if evaluation of proposed changes. **Supported only for concentration.** |

## Attribution

| term | in one line |
|---|---|
| **attribution** | which exposures drove a metric, rather than what the metric was |
| **active risk** | risk taken relative to the benchmark, as opposed to total risk |
| **stateless path** | the caller supplies the full history in the request |
| **stateful path** | the service assembles history from upstream sources |
| **grouping dimension** | how attribution is decomposed: `POSITION`, `ISSUER`, `SECTOR`, `ASSET_CLASS` or `CUSTOM` |
| **issuer group** | the benchmark exposure grouping the `ISSUER` dimension uses, sourced from `lotus-performance` |

Stateful `ACTIVE_RISK` attribution supports `POSITION`, `SECTOR`, `ASSET_CLASS` and `ISSUER`.
**`CUSTOM` is the one rejected dimension** on the stateful path, with an explicit validation error.
See [API Surface](./API-Surface.md#current-limits).

## Evaluation surfaces

| term | in one line |
|---|---|
| **regime scenario pack** | a governed set of scenarios evaluated together, rather than ad-hoc stress inputs |
| **risk-event cohort** | the set of portfolios a given risk event affects |
| **mandate risk health** | whether a portfolio is inside its mandate's risk expectations, reported on `TRACKING_ERROR` |

## Answer quality

The words that say whether a number can be relied on. All three sets are closed, so a consumer can
branch on them mechanically.

| term | meaning |
|---|---|
| **supportability state** | `ready`, `stale`, `degraded`, `empty`, `error`, `permission_blocked`, `unsupported` |
| **`empty` vs `error`** | `empty` — the calculation ran and had nothing to work on. `error` — it could not run. |
| **`insufficient_observations`** | not enough history |
| **`insufficient_aligned_observations`** | portfolio and benchmark history did not overlap enough. A different problem, and a different fix. |
| **`benchmark_unavailable`** | a benchmark-dependent metric was requested without a usable benchmark |
| **`unsupported_input_mode`** | the request shape is not supported for this workflow — the answer `/integration/capabilities` would have given in advance |
| **freshness bucket** | `current`, `same_day`, `stale`, `unknown` — how recent the underlying observations are |
| **lineage** | the record of which upstream sources and versions produced an answer |

## Contract and operating words

| term | meaning |
|---|---|
| **capability publication** | `GET /integration/capabilities`, the authoritative statement of what this deployment supports |
| **endpoint matrix** | the per-endpoint support table read alongside capability publication; together they are the support contract |
| **canonical portfolio** | `PB_SG_GLOBAL_BAL_001`, the default subject of live validation |
| **trusted ingress** | the `X-Lotus-Trusted-Ingress` marker injected by the approved gateway; required for protected operator endpoints and writes, not for health probes |
| **draining** | the shutdown posture entered before downstream connection pools are closed |
| **report-only gate** | a quality gate that produces evidence without failing the build. Evidence for prioritisation, not proof of readiness. |

## Read next

1. [API Surface](./API-Surface.md) — where these names appear in the contract
2. [Overview](./Overview.md) — what the service owns
3. [Mesh Data Products](./Mesh-Data-Products.md) — how risk output is published
