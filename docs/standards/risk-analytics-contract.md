# Risk Analytics Contract Standard

## Endpoints
- `GET /ops`
- `POST /analytics/risk/calculate`
- `POST /analytics/risk/concentration`
- `GET /integration/capabilities`

## Integration Capabilities Contract
- `sourceService`: `lotus-risk`
- `policyVersion`: `risk.v1`
- `supportedInputModes`: `["stateless", "stateful", "simulation"]`
- `features`:
  - `risk.analytics.risk_analytics`
  - `risk.analytics.concentration`
  - `risk.analytics.metrics`
- `workflows`:
  - `risk_snapshot`
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

## Drawdown Details
- `max_drawdown`
- `peak_date`
- `trough_date`
- `max_drawdown_date` (compatibility alias to trough date)

## Concentration Risk
- Concentration endpoint computes HHI-based concentration metrics from current/projected positions.
- Returns `hhiCurrent`, `hhiProposed`, and `hhiDelta` under `riskProxy`.

## Error Semantics
- Standard envelope:
  - `error.code`
  - `error.message`
  - `error.correlationId`
  - optional `error.details`
- Period/model validation errors return `422` with `error.code=INVALID_REQUEST`.
- Calculation-level invalid period or method errors return `400` with `error.code=INVALID_INPUT`.
