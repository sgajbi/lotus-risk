# Risk Analytics Contract Standard

## Endpoints
- `GET /ops`
- `POST /analytics/risk/calculate`
- `POST /analytics/risk/drawdown`
- `POST /analytics/risk/rolling-metrics`
- `POST /analytics/risk/historical-attribution`
- `POST /analytics/risk/concentration`
- `GET /integration/capabilities`

## Integration Capabilities Contract
- `sourceService`: `lotus-risk`
- `policyVersion`: `risk.v1`
- `supportedInputModes`: `["stateless", "stateful", "simulation"]`
- `features`:
  - `risk.analytics.risk_analytics`
  - `risk.analytics.drawdown`
  - `risk.analytics.rolling_metrics`
  - `risk.analytics.historical_attribution`
  - `risk.analytics.concentration`
  - `risk.analytics.metrics`
  - `risk.observability.calculation_supportability`
- `workflows`:
  - `risk_snapshot`
  - `drawdown_analytics`
  - `rolling_risk_analytics`
  - `historical_risk_attribution`
  - `concentration_risk`

## Supported Period Types
- `EXPLICIT`: requires `from/to` (`fromDate` and `toDate` also supported).
- `YEAR`: requires `year`.
- Canonical: `MTD`, `QTD`, `YTD`, `1Y`, `3Y`, `5Y`, `SI`.

## Compatibility Normalization
- Accepted aliases normalized internally:
- `CUSTOM` -> `EXPLICIT`
- `ONE_YEAR` -> `1Y`
- `THREE_YEAR` -> `3Y`
- `FIVE_YEAR` -> `5Y`
- `ITD` -> `SI`

## VaR Methods
- `HISTORICAL`
- `GAUSSIAN`
- `CORNISH_FISHER`
- Horizon scaling uses `sqrt(horizonDays)`.
- Expected shortfall is optional and returned in `details.expected_shortfall`.

## Benchmark-Dependent Metrics
- Metrics: `BETA`, `TRACKING_ERROR`, `INFORMATION_RATIO`.
- If benchmark returns are missing, API returns deterministic metric payloads:
- `value: null`
- `details.error: "Benchmark returns required for benchmark-dependent metric"`

## Calculation Supportability
- `POST /analytics/risk/calculate`, `POST /analytics/risk/drawdown`,
  `POST /analytics/risk/rolling-metrics`, `POST /analytics/risk/historical-attribution`, and
  `POST /analytics/risk/concentration` emit `metadata.calculation_supportability`.
- Supported states: `ready`, `stale`, `degraded`, `empty`, `error`, `permission_blocked`, `unsupported`.
- Supported freshness buckets: `current`, `same_day`, `stale`, `unknown`.
- Supported reasons include `calculation_complete`, `benchmark_unavailable`, `calculation_quality_issue`,
  `insufficient_aligned_observations`, `insufficient_observations`, `no_return_observations`,
  `permission_blocked`, `stale_source_observations`, and `unsupported_input_mode`.
- Prometheus exports the same posture through `lotus_risk_calculation_supportability_total` with
  bounded labels only: `operation`, `supportability_state`, `reason`, and `freshness_bucket`.
- The response contract publishes these keys as `metric_labels` so operators, Gateway, Workbench,
  and demos can inspect the supportability metric contract without inferring it from scrape output.
- Metrics and response metadata must not expose portfolio, client, account, position, transaction,
  security, trace, correlation, request-body, response-body, or raw request identifiers.
- Endpoint-specific supportability must be source-backed: return-series endpoints derive freshness
  and empty/degraded posture from period results, historical-attribution also degrades when any
  attribution set emits quality flags, and concentration derives degraded posture from issuer
  coverage and empty universe support.

## Risk Calculate Mode Support
- `stateless`: caller supplies full return series.
- `stateful`: caller supplies identifiers + risk metric specification; lotus-risk sources canonical portfolio/benchmark/risk-free series from lotus-performance (`/integration/returns/series`, `input_mode=stateful`, `stateful_input is an empty envelope; consumer identity is stamped by lotus-performance server-side`) and computes with the same engine.
- `simulation`: intentionally unsupported by contract for `risk/calculate`; concentration is the only simulation-enabled risk flow.

## Drawdown Details
- `max_drawdown`
- `peak_date`
- `trough_date`
- `max_drawdown_date` (compatibility alias to trough date)

## Realized Drawdown Endpoint
- `POST /analytics/risk/drawdown` supports:
  - `stateless`: caller supplies return series
  - `stateful`: lotus-risk resolves canonical returns through lotus-performance stateful integration mode
  - `simulation`: intentionally unsupported by contract
- Output includes:
  - period-level drawdown summary (`max_drawdown`, timing, TUW, ulcer index, DaR/CDaR)
  - worst drawdown episodes list (policy-driven top-N)
  - optional underwater series and benchmark-relative summary

## Rolling Metrics Endpoint
- `POST /analytics/risk/rolling-metrics` supports:
  - `stateless`: caller supplies return/reference series and rolling options
  - `stateful`: caller supplies identifiers and options; lotus-risk sources portfolio and benchmark returns from lotus-performance and risk-free series from lotus-core as required by requested metrics
  - `simulation`: intentionally unsupported by contract
- Output includes:
  - per-window summaries for rolling volatility, Sharpe, beta, tracking error, information ratio, and rolling max drawdown
  - optional rolling time-series points
  - deterministic quality flags for non-computable windows/alignments

## Historical Attribution Endpoint
- `POST /analytics/risk/historical-attribution` supports:
  - `stateless`: caller supplies portfolio/benchmark return series plus exposure history by grouping dimension
  - `stateful`: implemented for total risk and active risk with supported grouping dimensions; portfolio/benchmark returns and benchmark exposure context come from lotus-performance, portfolio exposure history and enrichment come from lotus-core
  - `simulation`: intentionally unsupported by contract
- Output includes:
  - period-level attribution decomposition sets for total risk and active risk
  - contributor-level `weight_average`, `marginal_contribution`, `component_contribution`, `percent_contribution`
  - reconciliation controls: `total_value`, `reconciled_sum`, `residual`, and `quality_flags`

## Concentration Risk
- Concentration endpoint supports all execution modes:
  - `stateless`: caller supplies positions
  - `stateful`: caller supplies identifiers; lotus-risk resolves baseline from lotus-core
  - `simulation`: caller supplies identifiers and BUY/SELL simulation changes; lotus-risk validates the operation vocabulary and required positive `quantity` or `amount` before orchestrating lotus-core session and snapshot APIs
- Response includes:
  - `risk_proxy`: `hhi_current`, `hhi_proposed`, `hhi_delta`
  - `single_position_concentration`: top-position and top-N concentration metrics
  - `valuation_context` and `metadata` for stateful/simulation executions

## Error Semantics
- All documented risk endpoints expose standard OpenAPI error contracts for:
  - `400`
  - `424`
  - `403`
  - `404`
  - `422`
  - `502`
  - `503`
  - `504`
- Error envelope:
  - `error.type`
  - `error.title`
  - `error.status`
  - `error.detail`
  - `error.instance`
  - `error.code`
  - `error.message`
  - `error.correlation_id`
  - optional `error.details`
- `error.type`, `error.title`, `error.status`, `error.detail`, and `error.instance` are additive
  RFC 7807/problem-details compatibility fields inside the existing Lotus `error` object.
- `error.code` remains the stable Lotus machine-readable error code.
- Period/model validation errors return `422` with `error.code=INVALID_REQUEST`.
- Calculation-level invalid period or method errors return `400` with `error.code=INVALID_INPUT`.
- Dependency rejection or missing upstream-required data returns `424` with `error.code=FAILED_DEPENDENCY`.
- Dependency malformed payloads and upstream server failures return `502` with `error.code=UPSTREAM_INVALID_RESPONSE` or `UPSTREAM_FAILURE`.
- Dependency transport unavailability returns `503` with `error.code=UPSTREAM_UNAVAILABLE`.
- Dependency timeout returns `504` with `error.code=UPSTREAM_TIMEOUT`.

