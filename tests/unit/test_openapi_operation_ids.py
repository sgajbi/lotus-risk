from fastapi.testclient import TestClient

from app.main import app


EXPECTED_ANALYTICS_OPERATION_IDS = {
    "/analytics/risk/calculate": "calculateRiskAnalytics",
    "/analytics/risk/concentration": "calculateConcentrationRiskAnalytics",
    "/analytics/risk/drawdown": "calculateDrawdownAnalytics",
    "/analytics/risk/historical-attribution": "calculateHistoricalRiskAttribution",
    "/analytics/risk/mandate-health-context": "evaluateMandateRiskHealthContext",
    "/analytics/risk/regime-scenario-pack/evaluate": "evaluateRegimeScenarioPack",
    "/analytics/risk/risk-event-cohorts/evaluate": "evaluateRiskEventAffectedCohort",
    "/analytics/risk/rolling-metrics": "calculateRollingRiskMetrics",
}


def test_public_analytics_routes_have_stable_operation_ids() -> None:
    spec = TestClient(app).get("/openapi.json").json()

    for path, operation_id in EXPECTED_ANALYTICS_OPERATION_IDS.items():
        assert spec["paths"][path]["post"]["operationId"] == operation_id


def test_openapi_operation_ids_are_unique() -> None:
    spec = TestClient(app).get("/openapi.json").json()
    operation_ids = [
        operation["operationId"]
        for path_item in spec["paths"].values()
        for operation in path_item.values()
        if "operationId" in operation
    ]

    assert len(operation_ids) == len(set(operation_ids))
