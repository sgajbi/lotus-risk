from fastapi.testclient import TestClient

from app.main import app
from tests.support.app_runtime import override_app_runtime
from tests.support.lotus_core_fakes import SimulationLotusCoreClient


def test_health_endpoints() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert client.get("/ops").status_code == 200


def test_correlation_header_propagation() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Correlation-Id": "corr-123"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-123"


def test_integration_capabilities_contract() -> None:
    client = TestClient(app)
    response = client.get("/integration/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["source_service"] == "lotus-risk"
    assert body["policy_version"] == "risk.v1"
    assert body["supported_input_modes"] == ["stateless", "stateful", "simulation"]
    assert isinstance(body["features"], list)
    assert isinstance(body["workflows"], list)
    feature_keys = {feature["key"] for feature in body["features"]}
    assert feature_keys == {
        "risk.analytics.risk_analytics",
        "risk.analytics.concentration",
        "risk.analytics.drawdown",
        "risk.analytics.rolling_metrics",
        "risk.analytics.historical_attribution",
        "risk.analytics.metrics",
    }
    workflow_keys = {workflow["workflow_key"] for workflow in body["workflows"]}
    assert workflow_keys == {
        "risk_snapshot",
        "concentration_risk",
        "drawdown_analytics",
        "rolling_risk_analytics",
        "historical_risk_attribution",
    }


def _concentration_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "current_positions": [
                {"security_id": "A", "quantity": 10},
                {"security_id": "B", "quantity": 10},
            ],
            "projected_positions": [
                {"security_id": "A", "proposed_quantity": 15},
                {"security_id": "B", "proposed_quantity": 5},
            ],
        },
    }


def test_concentration_risk_endpoint() -> None:
    with override_app_runtime(
        lotus_core_client=SimulationLotusCoreClient(
            session_id="SIM_HEALTH_0001",
            simulation_version=1,
        )
    ):
        client = TestClient(app)
        response = client.post("/analytics/risk/concentration", json=_concentration_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source_service"] == "lotus-risk"
    assert "risk_proxy" in body
    assert body["risk_proxy"]["hhi_current"] > 0


def test_legacy_workbench_proxy_removed_with_standard_404_error() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/workbench/risk-proxy",
        json=_concentration_payload(),
        headers={"X-Correlation-Id": "corr-legacy-404"},
    )
    assert response.status_code == 404
    assert response.headers["X-Correlation-Id"] == "corr-legacy-404"
    body = response.json()["error"]
    assert body["code"] == "RESOURCE_NOT_FOUND"
    assert body["correlation_id"] == "corr-legacy-404"


def test_concentration_handles_non_positive_positions() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/concentration",
        json={
            "input_mode": "stateless",
            "stateless_input": {
                "current_positions": [{"security_id": "A", "quantity": 0}],
                "projected_positions": [{"security_id": "B", "proposed_quantity": -5}],
            },
        },
    )
    assert response.status_code == 200
    proxy = response.json()["risk_proxy"]
    assert proxy["hhi_current"] == 0
    assert proxy["hhi_proposed"] == 0
    assert proxy["hhi_delta"] == 0


def test_openapi_hides_legacy_proxy_and_exposes_concentration() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    assert "/analytics/risk/concentration" in spec["paths"]
    assert "/analytics/risk/historical-attribution" in spec["paths"]
    assert "/analytics/risk/drawdown" in spec["paths"]
    assert "/analytics/risk/rolling-metrics" in spec["paths"]
    assert "/ops" in spec["paths"]
    assert "/analytics/workbench/risk-proxy" not in spec["paths"]


def test_metadata_and_ops_contract_shape() -> None:
    client = TestClient(app)
    metadata = client.get("/metadata")
    ops = client.get("/ops")
    assert metadata.status_code == 200
    assert ops.status_code == 200
    metadata_body = metadata.json()
    ops_body = ops.json()
    assert metadata_body["service"] == "lotus-risk"
    assert metadata_body["version"] == "0.1.0"
    assert "rounding_policy_version" in metadata_body
    assert ops_body["status"] == "ok"
    assert ops_body["checks"]["live"] is True
    assert ops_body["checks"]["ready"] is True
    assert ops_body["checks"]["draining"] is False
    assert ops_body["input_modes"] == ["stateless", "stateful", "simulation"]
    assert [dependency["service"] for dependency in ops_body["dependencies"]] == [
        "lotus-core",
        "lotus-performance",
    ]
    assert all(dependency["status"] == "ok" for dependency in ops_body["dependencies"])
    assert all(dependency["category"] is None for dependency in ops_body["dependencies"])
    assert all(dependency["issue_code"] is None for dependency in ops_body["dependencies"])


def test_health_ready_and_ops_surface_dependency_degradation() -> None:
    with override_app_runtime(
        dependency_statuses={
            "lotus-performance": {
                "status": "degraded",
                "detail": "high_latency",
                "category": "transport",
                "issue_code": "UPSTREAM_HIGH_LATENCY",
            }
        }
    ):
        client = TestClient(app)
        readiness = client.get("/health/ready")
        ops = client.get("/ops")

    assert readiness.status_code == 200
    assert readiness.json()["status"] == "degraded"
    assert ops.status_code == 200
    ops_body = ops.json()
    assert ops_body["status"] == "degraded"
    assert ops_body["checks"]["ready"] is True
    performance_dependency = next(
        dependency
        for dependency in ops_body["dependencies"]
        if dependency["service"] == "lotus-performance"
    )
    assert performance_dependency["detail"] == "high_latency"
    assert performance_dependency["category"] == "transport"
    assert performance_dependency["issue_code"] == "UPSTREAM_HIGH_LATENCY"


def test_health_ready_fails_when_dependency_is_unavailable() -> None:
    with override_app_runtime(
        dependency_statuses={
            "lotus-core": {"status": "unavailable", "detail": "connection_refused"}
        }
    ):
        client = TestClient(app)
        readiness = client.get("/health/ready")
        ops = client.get("/ops")

    assert readiness.status_code == 503
    readiness_body = readiness.json()
    assert readiness_body["status"] == "dependency_unavailable"
    assert any(
        dependency["service"] == "lotus-core" and dependency["status"] == "unavailable"
        for dependency in readiness_body["dependencies"]
    )
    assert ops.json()["checks"]["ready"] is False


def test_health_ready_and_ops_surface_structured_data_gap_metadata() -> None:
    with override_app_runtime(
        dependency_statuses={
            "lotus-core": {
                "status": "degraded",
                "detail": "risk_free_series_missing_for_usd_ytd",
                "category": "data_gap",
                "issue_code": "RISK_FREE_SERIES_EMPTY",
            }
        }
    ):
        client = TestClient(app)
        readiness = client.get("/health/ready")
        ops = client.get("/ops")

    assert readiness.status_code == 200
    readiness_dependency = next(
        dependency
        for dependency in readiness.json()["dependencies"]
        if dependency["service"] == "lotus-core"
    )
    assert readiness_dependency["status"] == "degraded"
    assert readiness_dependency["category"] == "data_gap"
    assert readiness_dependency["issue_code"] == "RISK_FREE_SERIES_EMPTY"

    ops_dependency = next(
        dependency
        for dependency in ops.json()["dependencies"]
        if dependency["service"] == "lotus-core"
    )
    assert ops_dependency["detail"] == "risk_free_series_missing_for_usd_ytd"
    assert ops_dependency["category"] == "data_gap"
    assert ops_dependency["issue_code"] == "RISK_FREE_SERIES_EMPTY"


def test_openapi_declares_standard_error_models_for_risk_endpoints() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    calculate_responses = spec["paths"]["/analytics/risk/calculate"]["post"]["responses"]
    concentration_responses = spec["paths"]["/analytics/risk/concentration"]["post"]["responses"]
    attribution_responses = spec["paths"]["/analytics/risk/historical-attribution"]["post"][
        "responses"
    ]
    drawdown_responses = spec["paths"]["/analytics/risk/drawdown"]["post"]["responses"]
    rolling_responses = spec["paths"]["/analytics/risk/rolling-metrics"]["post"]["responses"]

    for responses in (
        calculate_responses,
        concentration_responses,
        attribution_responses,
        drawdown_responses,
        rolling_responses,
    ):
        for status_code in ("400", "403", "404", "422", "424", "502", "503", "504"):
            schema_ref = responses[status_code]["content"]["application/json"]["schema"]["$ref"]
            assert schema_ref.endswith("/ErrorResponse")
        assert responses["400"]["content"]["application/json"]["example"]["error"]["code"] == (
            "INVALID_INPUT"
        )
        assert responses["403"]["content"]["application/json"]["example"]["error"]["code"] == (
            "AUTHORIZATION_DENIED"
        )
        assert responses["404"]["content"]["application/json"]["example"]["error"]["code"] == (
            "RESOURCE_NOT_FOUND"
        )
        assert responses["422"]["content"]["application/json"]["example"]["error"]["code"] == (
            "INVALID_REQUEST"
        )
        assert responses["424"]["content"]["application/json"]["example"]["error"]["code"] == (
            "FAILED_DEPENDENCY"
        )
        assert responses["502"]["content"]["application/json"]["example"]["error"]["code"] == (
            "UPSTREAM_FAILURE"
        )
        assert responses["503"]["content"]["application/json"]["example"]["error"]["code"] == (
            "UPSTREAM_UNAVAILABLE"
        )
        assert responses["504"]["content"]["application/json"]["example"]["error"]["code"] == (
            "UPSTREAM_TIMEOUT"
        )


def test_openapi_exposes_typed_capabilities_response_contract() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    capabilities_get = spec["paths"]["/integration/capabilities"]["get"]
    schema_ref = capabilities_get["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ]
    assert schema_ref.endswith("/IntegrationCapabilitiesResponse")


def test_drawdown_openapi_examples_are_present_and_canonical() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    drawdown_schema = spec["components"]["schemas"]["DrawdownAnalyticsRequest"]
    response_schema = spec["components"]["schemas"]["DrawdownResponse"]

    assert drawdown_schema["properties"]["input_mode"]["example"] == "stateful"
    assert (
        drawdown_schema["properties"]["stateful_input"]["example"]["benchmark_policy"][
            "include_benchmark"
        ]
        is True
    )
    assert (
        drawdown_schema["properties"]["analysis_options"]["example"]["top_n_episodes"] == 5
    )
    assert response_schema["properties"]["metadata"]["example"]["missing_benchmark_policy"] in {
        "IGNORE",
        "REQUIRE",
    }
    assert response_schema["properties"]["results"]["example"]["YTD"]["summary"][
        "max_drawdown"
    ] < 0


def test_risk_calculate_openapi_examples_are_present_and_canonical() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    request_schema = spec["components"]["schemas"]["RiskAnalyticsRequest"]
    response_schema = spec["components"]["schemas"]["RiskResponse"]

    assert request_schema["properties"]["input_mode"]["example"] == "stateless"
    assert (
        request_schema["properties"]["stateful_input"]["example"]["metrics"]
        == ["VOLATILITY", "BETA", "TRACKING_ERROR", "INFORMATION_RATIO"]
    )
    assert (
        request_schema["properties"]["stateful_input"]["example"]["options"]["var"][
            "horizon_days"
        ]
        == 4
    )
    assert (
        response_schema["example"]["results"]["YTD"]["metrics"]["VAR"]["details"][
            "horizon_scale_method"
        ]
        == "SQRT_TIME"
    )
    assert (
        response_schema["example"]["results"]["YTD"]["metrics"]["INFORMATION_RATIO"][
            "details"
        ]["annualized_active_return"]
        > 0
    )
    assert response_schema["example"]["metadata"]["var_horizon_days"] == 4


def test_rolling_openapi_examples_are_present_and_canonical() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    request_schema = spec["components"]["schemas"]["RollingAnalyticsRequest"]
    response_schema = spec["components"]["schemas"]["RollingResponse"]

    assert request_schema["properties"]["input_mode"]["example"] == "stateless"
    assert request_schema["properties"]["stateful_input"]["example"]["rolling_options"][
        "window_lengths"
    ] == [21, 63]
    assert request_schema["properties"]["stateful_input"]["example"]["rolling_options"][
        "metrics"
    ] == [
        "ROLLING_VOLATILITY",
        "ROLLING_BETA",
        "ROLLING_TRACKING_ERROR",
    ]
    assert response_schema["example"]["input_mode"] == "stateful"
    assert response_schema["example"]["results"]["YTD"]["benchmark_series_count"] == 90
    assert response_schema["example"]["results"]["YTD"]["aligned_benchmark_series_count"] == 90
    assert response_schema["example"]["results"]["YTD"]["risk_free_series_count"] == 0
    assert response_schema["example"]["results"]["YTD"]["aligned_risk_free_series_count"] == 0
    assert response_schema["example"]["results"]["YTD"]["benchmark_context"]["reason"] == "APPLIED"
    assert response_schema["example"]["results"]["YTD"]["risk_free_context"]["reason"] == "NOT_REQUESTED"
    assert response_schema["example"]["metadata"]["benchmark_context"]["requested"] is True
    assert response_schema["example"]["metadata"]["risk_free_context"]["requested"] is False
    assert response_schema["example"]["results"]["YTD"]["window_results"][0]["window_length"] == 21
    assert (
        response_schema["example"]["results"]["YTD"]["window_results"][0]["metric_summaries"][
            "ROLLING_VOLATILITY"
        ]["total_point_count"]
        == 90
    )
    assert (
        response_schema["example"]["results"]["YTD"]["window_results"][0]["metric_summaries"][
            "ROLLING_VOLATILITY"
        ]["computed_point_count"]
        > 0
    )
    assert (
        response_schema["example"]["results"]["YTD"]["window_results"][0]["metric_summaries"][
            "ROLLING_VOLATILITY"
        ]["coverage_ratio"]
        > 0
    )
    assert (
        response_schema["example"]["results"]["YTD"]["window_results"][0]["metric_summaries"][
            "ROLLING_TRACKING_ERROR"
        ]["latest"]
        > 0
    )
    assert response_schema["example"]["metadata"]["alignment_policy"] == "INNER_JOIN"


def test_concentration_rejects_legacy_payload_shape() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/concentration",
        json={
            "current_positions": [{"security_id": "A", "quantity": 10}],
            "projected_positions": [{"security_id": "B", "proposed_quantity": 5}],
        },
    )
    assert response.status_code == 422


def test_concentration_stateful_mode_uses_lotus_core_snapshot() -> None:
    with override_app_runtime(
        lotus_core_client=SimulationLotusCoreClient(
            session_id="SIM_0001",
            simulation_version=3,
        )
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/concentration",
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-02-27",
                },
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateful"
    assert body["risk_proxy"]["hhi_current"] == 6800.0
    assert body["metadata"]["portfolio_id"] == "DEMO_DPM_EUR_001"
    assert body["metadata"]["issuer_grouping_level"] == "ultimate_parent"
    assert body["metadata"]["enrichment_policy"] == "merge_caller_then_core"


def test_concentration_simulation_mode_reuses_or_creates_session_and_returns_metadata() -> None:
    with override_app_runtime(
        lotus_core_client=SimulationLotusCoreClient(
            session_id="SIM_0001",
            simulation_version=3,
        )
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/concentration",
            json={
                "input_mode": "simulation",
                "simulation_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-02-27",
                    "simulation_changes": [
                        {"security_id": "SEC_A", "transaction_type": "BUY", "quantity": 10}
                    ],
                },
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "simulation"
    assert body["risk_proxy"]["hhi_current"] == 5200.0
    assert body["risk_proxy"]["hhi_proposed"] == 8200.0
    assert body["metadata"]["simulation_session_id"] == "SIM_0001"
    assert body["metadata"]["simulation_session_version"] == 3
    assert body["metadata"]["issuer_grouping_level"] == "ultimate_parent"
    assert body["metadata"]["enrichment_policy"] == "merge_caller_then_core"
