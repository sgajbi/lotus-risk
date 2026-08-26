from fastapi.testclient import TestClient

from app.main import app

EXPECTED_OPERATION_IDS = {
    ("get", "/health"): "getHealthStatus",
    ("get", "/health/live"): "getLivenessStatus",
    ("get", "/health/ready"): "getReadinessStatus",
    ("get", "/integration/capabilities"): "getIntegrationCapabilities",
    ("get", "/metadata"): "getServiceMetadata",
    ("get", "/metrics"): "getPrometheusMetrics",
    ("get", "/ops"): "getOperationalDiagnostics",
    ("get", "/ops/trust-telemetry"): "getTrustTelemetrySnapshot",
    ("post", "/analytics/risk/calculate"): "calculateRiskAnalytics",
    ("post", "/analytics/risk/concentration"): "calculateConcentrationRiskAnalytics",
    ("post", "/analytics/risk/drawdown"): "calculateDrawdownAnalytics",
    ("post", "/analytics/risk/historical-attribution"): "calculateHistoricalRiskAttribution",
    ("post", "/analytics/risk/mandate-health-context"): "evaluateMandateRiskHealthContext",
    ("post", "/analytics/risk/regime-scenario-pack/evaluate"): "evaluateRegimeScenarioPack",
    ("post", "/analytics/risk/risk-event-cohorts/evaluate"): "evaluateRiskEventAffectedCohort",
    ("post", "/analytics/risk/rolling-metrics"): "calculateRollingRiskMetrics",
}


def test_openapi_routes_have_stable_operation_ids() -> None:
    spec = TestClient(app).get("/openapi.json").json()

    for (method, path), operation_id in EXPECTED_OPERATION_IDS.items():
        assert spec["paths"][path][method]["operationId"] == operation_id


def test_openapi_operation_ids_are_unique() -> None:
    spec = TestClient(app).get("/openapi.json").json()
    operation_ids = [
        operation["operationId"]
        for path_item in spec["paths"].values()
        for operation in path_item.values()
        if "operationId" in operation
    ]

    assert len(operation_ids) == len(set(operation_ids))
