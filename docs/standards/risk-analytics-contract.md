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
- `workflows`:
  - `risk_snapshot`
  - `drawdown_analytics`
  - `rolling_risk_analytics`
  - `historical_risk_attribution`
  - `concentration_risk`

## Supported Period Types
- `EXPLICIT`: requires `from/to` (`fromDate` and `toDate` also supported).
- `YEAR`: requires `year`.
- Standard: `MTD`, `QTD`, `YTD`, `ONE_YEAR`, `THREE_YEAR`, `FIVE_YEAR`, `SI`.

## Compatibility Normalization
- Accepted aliases normalized internally:
- `CUSTOM` -> `EXPLICIT`
- `1Y` -> `ONE_YEAR`
- `3Y` -> `THREE_YEAR`
- `5Y` -> `FIVE_YEAR`

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

## Risk Calculate Mode Support
- `stateless`: caller supplies full return series.
- `stateful`: caller supplies identifiers + risk metric specification; lotus-risk sources canonical portfolio/benchmark/risk-free series from lotus-performance (`/integration/returns/series`, `input_mode=stateful`, `stateful_input.consumer_system=lotus-risk`) and computes with the same engine.
- `simulation`: reserved and not implemented for risk/calculate.

## Drawdown Details
- `max_drawdown`
- `peak_date`
- `trough_date`
- `max_drawdown_date` (compatibility alias to trough date)

## Realized Drawdown Endpoint
- `POST /analytics/risk/drawdown` supports:
  - `stateless`: caller supplies return series
  - `stateful`: lotus-risk resolves canonical returns through lotus-performance stateful integration mode
  - `simulation`: reserved/not yet implemented
- Output includes:
  - period-level drawdown summary (`max_drawdown`, timing, TUW, ulcer index, DaR/CDaR)
  - worst drawdown episodes list (policy-driven top-N)
  - optional underwater series and benchmark-relative summary

## Rolling Metrics Endpoint
- `POST /analytics/risk/rolling-metrics` supports:
  - `stateless`: caller supplies return/reference series and rolling options
  - `stateful`: caller supplies identifiers and options; lotus-risk sources canonical portfolio/benchmark/risk-free series from lotus-performance as required by requested metrics
  - `simulation`: reserved/not yet implemented
- Output includes:
  - per-window summaries for rolling volatility, Sharpe, beta, tracking error, information ratio, and rolling max drawdown
  - optional rolling time-series points
  - deterministic quality flags for non-computable windows/alignments

## Historical Attribution Endpoint
- `POST /analytics/risk/historical-attribution` supports:
  - `stateless`: caller supplies portfolio/benchmark return series plus exposure history by grouping dimension
  - `stateful`: reserved/not yet implemented in Slice A
  - `simulation`: reserved/not yet implemented
- Output includes:
  - period-level attribution decomposition sets for total risk and active risk
  - contributor-level `weight_average`, `marginal_contribution`, `component_contribution`, `percent_contribution`
  - reconciliation controls: `total_value`, `reconciled_sum`, `residual`, and `quality_flags`

## Concentration Risk
- Concentration endpoint supports all execution modes:
  - `stateless`: caller supplies positions
  - `stateful`: caller supplies identifiers; lotus-risk resolves baseline from lotus-core
  - `simulation`: caller supplies identifiers and simulation changes; lotus-risk orchestrates lotus-core session and snapshot APIs
- Response includes:
  - `risk_proxy`: `hhi_current`, `hhi_proposed`, `hhi_delta`
  - `single_position_concentration`: top-position and top-N concentration metrics
  - `valuation_context` and `metadata` for stateful/simulation executions

## Error Semantics
- All documented risk endpoints expose standard OpenAPI error contracts for:
  - `400`
  - `403`
  - `404`
  - `422`
- Error envelope:
  - `error.code`
  - `error.message`
  - `error.correlationId`
  - optional `error.details`
- Period/model validation errors return `422` with `error.code=INVALID_REQUEST`.
- Calculation-level invalid period or method errors return `400` with `error.code=INVALID_INPUT`.
