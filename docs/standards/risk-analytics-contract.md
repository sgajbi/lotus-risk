# Risk Analytics Contract Standard

## Endpoints
- `POST /analytics/risk/calculate`
- `POST /analytics/risk/concentration`

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
- Period/model validation errors return `422` (request validation layer).
- Calculation-level invalid period or method errors return `400`.
