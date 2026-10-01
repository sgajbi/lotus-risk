# Mandate Risk Health Context

## Endpoint

- `POST /analytics/risk/mandate-health-context`

## Purpose

`MandateRiskHealthContext:v1` gives downstream DPM consumers a bounded source-owned risk health
signal for mandate supportability. The first-wave implementation derives health posture from the
existing lotus-risk tracking-error methodology and preserves source ownership, threshold posture,
lineage fingerprints, and reason codes.

The endpoint does not create mandate actions, rebalance waves, approvals, client communications, OMS
orders, or execution instructions.

## Inputs

- `portfolio_id`
- `scope.as_of_date`
- one `period`
- `portfolio_open_date`
- portfolio `returns`
- `benchmark_returns`
- optional `tracking_error_attention_threshold` as an annualized decimal ratio

Return observations use the same percentage-point convention as `POST /analytics/risk/calculate`.
Portfolio and benchmark series each require one observation per date; repeated dates refuse with
`422 INVALID_REQUEST` before tracking-error alignment or health classification.

An empty portfolio history is a valid but unavailable source condition, not a zero tracking-error
observation: the endpoint returns `200` with `health_state: "unavailable"`,
`threshold_breached: null`, a null source metric, and
`MANDATE_RISK_HEALTH_PORTFOLIO_HISTORY_UNAVAILABLE`. An empty benchmark alone, out-of-period
history, or insufficient aligned evidence also remains unavailable without inferring a breach or
ready posture.

## Output Contract

The response publishes:

- `product_name: "MandateRiskHealthContext"`
- `product_version: "v1"`
- `health_state`: `ready`, `attention`, or `unavailable`
- `threshold_breached`
- `source_metric.annualized_tracking_error` as a decimal ratio
- `methodology_posture.source_metrics_product: "RiskMetricsReport:v1"`
- `methodology_posture.source_route: "/analytics/risk/calculate"`
- request and source-request fingerprints
- bounded reason codes, including `RISK_METHODOLOGY_SOURCE_OWNED`

## Supportability Boundary

This is intentionally a partial first-wave source product:

- supported: supplied-return stateless tracking-error health context
- unsupported: stateful mandate universe discovery
- unsupported: mandate action creation
- unsupported: wave orchestration
- unsupported: client communication or execution

