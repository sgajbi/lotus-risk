# Operations & Troubleshooting Guide: Risk Analytics

## 1. Summary

This guide provides operational instructions for monitoring, troubleshooting, and supporting the on-the-fly Risk Analytics feature within the `query-service`.

## 2. Key Dependencies

The Risk Analytics feature is a read-only process that relies entirely on data already persisted in the main PostgreSQL database. A failure or lack of data in these upstream tables will directly impact the availability and correctness of the risk calculations.

* **Primary Data Source**: The `portfolio_timeseries` table. If data is missing for a given portfolio and date range, risk calculations cannot be performed.

  **Ownership.** `portfolio_timeseries` is a `lotus-core` **source data product**, materialized by Core's derived-state capability — `portfolio_derived_state_service`, which owns both position-level (`position_timeseries`) and portfolio-level (`portfolio_timeseries`) materialization. Do not escalate against `timeseries-generator-service`: that runtime no longer exists in Core, and this guide previously named it. Escalate against the **product** and let Core route it, since Core owns its own topology and has consolidated these services once already.

  **Diagnosing absence.** Missing data here is a Core-side gap, not a Risk fault, and Risk must not infer a value for it. Distinguish, because they escalate differently:
  * *portfolio unknown to Core* — not a data gap;
  * *portfolio known, no timeseries for the requested range* — a materialization gap;
  * *timeseries present but stale relative to the requested as-of date* — a freshness gap.

  **What Risk reports, precisely.**

  *Escalate to the service the response names, not to Core by default.* The stateful series is
  fetched from `lotus-performance`'s `/integration/returns/series`, and
  `stateful_returns_series_parser.py` names `service="lotus-performance"` on failure. Core owns
  the underlying timeseries products, but the dependency that failed is Performance — go there
  first, and to Core only once Performance identifies an upstream gap.

  *Case 3 (stale) is always visible — but read `freshness_bucket`, not `state`.* Two fields, two
  behaviours, and conflating them is the mistake to avoid here. `state` and `reason` follow a
  precedence chain in `_period_supportability_outcome`: degraded, then empty, then stale, then
  ready — so a stale series that is also degraded reports `state="degraded"`. But
  `freshness_bucket` is computed separately and carried on the response regardless, so
  `freshness_bucket="stale"` is still there alongside it.

  So a degraded state does not hide staleness; it just is not what `state` names. Check
  `freshness_bucket` to answer the freshness question, and `state` to answer what stopped the
  calculation. They can both be informative at once.

  *Cases 1 and 2 are NOT distinguishable.* An absent or empty series is a dependency failure:
  `extract_required_portfolio_returns` raises as soon as `portfolio_returns` yields no points, so
  no `metadata.calculation_supportability` is produced. An unknown portfolio and a known
  portfolio with no materialized range look identical from here.

  *A throttled upstream is not a rejection.* HTTP 429 maps to HTTP 503 with
  `code="UPSTREAM_THROTTLED"`, `category="throttled"` and `retryable=true`. That is actionable
  and worth retrying; do not read it as a refused request.

  The finer supportability reasons apply where a series **exists but is insufficient**. Risk
  calculation supportability emits, from `supportability_periods.py`:
  `insufficient_observations`, `insufficient_aligned_observations`, `benchmark_unavailable`,
  `calculation_quality_issue` and `stale_source_observations`. `source_product_unavailable` is
  **not** one of them — it belongs to the separate source-observation path
  (`source_product_observation.py`).

  So establish the case against Core — is the portfolio known, is the range materialized, is the
  data fresh for the as-of date — and quote that in the escalation. Risk's response tells you the
  dependency failed, not why.
* **Benchmark Data Source**: The `market_prices` table. This is required **only** when benchmark-relative metrics (Beta, Tracking Error, Information Ratio) are requested.
* **Foreign Exchange Data**: The `fx_rates` table. This is required **only** when a benchmark's currency differs from the portfolio's reporting currency.

## 3. Observability & Monitoring

The feature exposes key Prometheus metrics via the `query-service`'s `/metrics` endpoint. These should be monitored to understand usage and performance.

| Metric Name                       | Type      | Labels          | Description & What to Watch For                                                                                                         |
|-----------------------------------|-----------|-----------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| `risk_metric_requested_total`     | `Counter` | `metric_name`   | Tracks how many times each specific risk metric has been requested. A sudden drop might indicate a client-side issue.                         |
| `risk_metric_duration_seconds`    | `Histogram` | `metric_name`   | Measures the latency of each individual metric calculation. A spike for a specific metric could indicate a performance issue. |
| `db_operation_latency_seconds`    | `Histogram` | `repository`, `method` | Monitors the latency of database calls. Watch for spikes where `repository` is `PerformanceRepository` or `MarketPriceRepository`.       |

## 4. Structured Logging & Tracing

All logs related to a single API request are tied together with a `correlation_id`. When troubleshooting, always ask for or find the `correlation_id` from the `X-Correlation-ID` response header.

**Example Log Flow for a Request:**

1.  **`INFO`**: `Starting risk calculation for portfolio RISK_INT_TEST_01`
    * Indicates the service has received the request and is beginning to process it.
2.  **`INFO`**: `Successfully calculated base daily returns for 3 days for portfolio RISK_INT_TEST_01.`
    * Confirms that the underlying TWR engine has successfully generated the return series.
3.  **`WARN`**: `Could not calculate Volatility for period 'TestPeriod': Insufficient data provided...`
    * A common, non-fatal warning. The service will continue and return `null` for this metric.
4.  **`ERROR`**: `An unexpected error occurred during risk calculation...`
    * Indicates a critical, unhandled error. The API will return a `500` status code. This requires developer investigation.

## 5. Common Failure Scenarios & Resolutions

| Scenario                                                     | Symptom(s) in API Response                                                                          | Key Log Message(s)                                                                           | Resolution / Action                                                                                                                              |
|--------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| **Portfolio Does Not Exist** | `404 Not Found` with detail `"Portfolio P_FAKE not found"`                                          | `Portfolio P_FAKE not found.` (Warning)                                                      | Verify the `portfolio_id` with the user. The ID in the URL is incorrect or has not been ingested.                                                |
| **Insufficient Time-Series Data** | Metrics are `null` with a `details` object containing `"error": "Insufficient data..."`             | `Could not calculate Volatility for period 'YTD': Insufficient data...` (Warning)            | **This is expected behavior.** Advise the user to request a longer time period or wait for more `portfolio_timeseries` data to be generated.     |
| **Benchmark Security ID Invalid or Has No Price Data** | Benchmark metrics (Beta, etc.) are `null`. Other metrics (Volatility, etc.) are calculated correctly. | `Benchmark security ID provided, but no return data could be generated.` (Warning)           | The user-provided `benchmark_security_id` is invalid or has no prices for the requested period. Advise the user to ingest the required market prices. |
| **Calculation Fails Unexpectedly** | `500 Internal Server Error`                                                                         | `An unexpected error occurred during risk calculation...` with a full traceback (Error)      | **Escalate to the development team.** Provide the full logs, `correlation_id`, and the request body that caused the failure.                  |