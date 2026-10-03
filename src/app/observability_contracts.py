from __future__ import annotations

RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS: tuple[str, ...] = (
    "operation",
    "supportability_state",
    "reason",
    "freshness_bucket",
)

RISK_ANALYTICS_FRESHNESS_METRIC_LABELS: tuple[str, ...] = (
    "service",
    "operation",
    "freshness_bucket",
    "supportability_state",
)

HTTP_REQUEST_HANDLER_VALUES: tuple[str, ...] = (
    "/ops",
    "/ops/trust-telemetry",
    "/health",
    "/health/live",
    "/health/ready",
    "/metadata",
    "/version",
    "/integration/capabilities",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/analytics/risk/calculate",
    "/analytics/risk/drawdown",
    "/analytics/risk/rolling-metrics",
    "/analytics/risk/historical-attribution",
    "/analytics/risk/concentration",
    "/analytics/risk/mandate-health-context",
    "/analytics/risk/regime-scenario-pack/evaluate",
    "/analytics/risk/regime-scenario-pack/jobs",
    "/analytics/risk/regime-scenario-pack/jobs/{job_id}",
    "/analytics/risk/regime-scenario-pack/jobs/{job_id}/contributions",
    "/analytics/risk/risk-event-cohorts/evaluate",
    "unmatched",
)
HTTP_REQUEST_METHOD_VALUES: tuple[str, ...] = (
    "GET",
    "HEAD",
    "POST",
    "PUT",
    "DELETE",
    "OPTIONS",
    "OTHER",
)
HTTP_REQUEST_STATUS_VALUES: tuple[str, ...] = (
    "1xx",
    "2xx",
    "3xx",
    "4xx",
    "5xx",
    "other",
)
