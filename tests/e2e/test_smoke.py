from fastapi.testclient import TestClient
import pytest

from app.main import app
from tests.support.app_runtime import override_app_runtime
from tests.support.historical_attribution_fakes import (
    RecordingHistoricalAttributionCoreClient,
    build_benchmark_exposure_context_response,
    build_stateful_attribution_returns_client,
)
from tests.support.lotus_core_fakes import SimulationLotusCoreClient
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import (
    JAN_2026_DRAWDOWN_BENCHMARK_RETURNS,
    JAN_2026_PORTFOLIO_RETURNS,
    JAN_2026_RISK_FREE_RETURNS,
    JAN_2026_ROLLING_BENCHMARK_RETURNS,
    build_returns_series_response,
)


def _risk_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
            "portfolio_open_date": "2024-01-01",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY", "VAR"],
            "returns": [
                {"date": "2025-01-02", "value": 0.8},
                {"date": "2025-01-03", "value": -0.2},
                {"date": "2025-01-06", "value": 0.3},
            ],
        },
    }


def _drawdown_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-02-28", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": -1.2},
                {"date": "2026-01-05", "value": 0.8},
                {"date": "2026-01-06", "value": -0.4},
                {"date": "2026-01-05", "value": 1.1},
            ],
        },
    }


def _rolling_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-08", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-05", "value": -2.0},
                {"date": "2026-01-06", "value": 0.5},
                {"date": "2026-01-05", "value": 1.2},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-05", "value": -1.5},
                {"date": "2026-01-06", "value": 0.4},
                {"date": "2026-01-05", "value": 1.0},
            ],
            "risk_free_returns": [
                {"date": "2026-01-02", "value": 0.01},
                {"date": "2026-01-05", "value": 0.01},
                {"date": "2026-01-06", "value": 0.01},
                {"date": "2026-01-05", "value": 0.01},
            ],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": ["ROLLING_VOLATILITY", "ROLLING_MAX_DRAWDOWN"],
            },
        },
    }


def _historical_attribution_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-05", "value": -0.4},
                {"date": "2026-01-06", "value": 0.3},
                {"date": "2026-01-05", "value": 0.6},
                {"date": "2026-01-06", "value": -0.2},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-05", "value": -0.3},
                {"date": "2026-01-06", "value": 0.2},
                {"date": "2026-01-05", "value": 0.4},
                {"date": "2026-01-06", "value": -0.1},
            ],
            "exposure_history": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "weight": 0.55,
                },
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "weight": 0.45,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "weight": 0.50,
                },
            ],
            "benchmark_exposure_history": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "weight": 0.48,
                },
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "weight": 0.52,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "weight": 0.47,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "weight": 0.53,
                },
            ],
            "attribution_options": {
                "attribution_types": ["TOTAL_RISK", "ACTIVE_RISK"],
                "metrics": ["VOLATILITY", "TRACKING_ERROR"],
                "grouping_dimensions": ["SECTOR"],
                "annualization_basis": 252,
            },
        },
    }


def test_e2e_smoke() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metadata_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/metadata")
    assert response.status_code == 200
    assert response.json()["service"].startswith("lotus-")


def test_integration_capabilities_endpoint_exposes_support_matrix() -> None:
    client = TestClient(app)
    response = client.get("/integration/capabilities")
    assert response.status_code == 200

    body = response.json()
    workflow_by_key = {workflow["workflow_key"]: workflow for workflow in body["workflows"]}

    assert workflow_by_key["concentration_risk"]["endpoint_path"] == "/analytics/risk/concentration"
    assert workflow_by_key["concentration_risk"]["supported_input_modes"] == [
        "stateless",
        "stateful",
        "simulation",
    ]
    assert workflow_by_key["concentration_risk"]["support_status"] == "full"
    assert workflow_by_key["historical_risk_attribution"]["support_status"] == "partial"
    assert (
        "issuer active-risk consumes lotus-performance benchmark exposure context issuer groups"
        in workflow_by_key["historical_risk_attribution"]["notes"]
    )


def test_e2e_ops_trust_telemetry_exposes_declared_products_and_summary() -> None:
    client = TestClient(app)
    response = client.get("/ops/trust-telemetry")
    assert response.status_code == 200

    body = response.json()
    assert body["service"] == "lotus-risk"
    assert (
        body["declaration_source"] == "contracts/domain-data-products/lotus-risk-products.v1.json"
    )
    assert (
        body["consumer_declaration_source"]
        == "contracts/domain-data-products/lotus-risk-consumers.v1.json"
    )
    assert body["summary"]["declared_product_count"] == 7
    assert body["summary"]["declared_dependency_count"] == 6
    assert [product["product_name"] for product in body["products"]] == [
        "RiskMetricsReport",
        "DrawdownAnalyticsReport",
        "RollingRiskMetricsReport",
        "HistoricalRiskAttributionReport",
        "ConcentrationRiskReport",
        "RegimeScenarioPackEvaluation",
        "RiskEventAffectedCohort",
    ]


def test_e2e_capabilities_expose_product_surface_safety_notes() -> None:
    client = TestClient(app)
    response = client.get("/integration/capabilities")
    assert response.status_code == 200

    workflow_by_key = {
        workflow["workflow_key"]: workflow for workflow in response.json()["workflows"]
    }

    assert (
        "VaR and expected shortfall are signed return-threshold metrics"
        in workflow_by_key["risk_snapshot"]["notes"]
    )
    assert (
        "attribution residual and reconciled_sum must be preserved with contributors"
        in workflow_by_key["historical_risk_attribution"]["notes"]
    )
    assert (
        "simulation is supported only for concentration risk"
        in workflow_by_key["concentration_risk"]["notes"]
    )


def test_e2e_non_concentration_endpoints_reject_simulation_mode() -> None:
    client = TestClient(app)

    for endpoint in (
        "/analytics/risk/calculate",
        "/analytics/risk/drawdown",
        "/analytics/risk/rolling-metrics",
        "/analytics/risk/historical-attribution",
    ):
        response = client.post(endpoint, json={"input_mode": "simulation"})
        assert response.status_code == 422, endpoint
        assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_e2e_risk_calculate_happy_path() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/calculate", json=_risk_payload())
    assert response.status_code == 200
    body = response.json()
    assert "YTD" in body["results"]
    metrics = body["results"]["YTD"]["metrics"]
    assert metrics["VOLATILITY"]["value"] is not None
    assert metrics["VAR"]["value"] is not None


def test_e2e_risk_calculate_volatility_public_contract() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/calculate",
        json={
            "input_mode": "stateless",
            "stateless_input": {
                "scope": {"as_of_date": "2026-01-03", "net_or_gross": "NET"},
                "portfolio_open_date": "2026-01-01",
                "periods": [{"type": "YTD", "name": "YTD"}],
                "metrics": ["VOLATILITY"],
                "options": {"frequency": "DAILY", "use_log_returns": False},
                "returns": [
                    {"date": "2026-01-01", "value": 1.00},
                    {"date": "2026-01-02", "value": -0.50},
                    {"date": "2026-01-03", "value": 0.20},
                ],
            },
        },
    )

    assert response.status_code == 200
    metric = response.json()["results"]["YTD"]["metrics"]["VOLATILITY"]
    assert metric["value"] == pytest.approx(11.914696806885186)
    assert metric["details"]["standard_deviation"] == pytest.approx(0.007505553499465135)
    assert metric["details"]["observation_count"] == 3
    assert metric["details"]["annualization_factor"] == 252


def test_e2e_risk_calculate_accepts_canonical_rolling_periods() -> None:
    client = TestClient(app)
    payload = _risk_payload()
    stateless_input = payload["stateless_input"]
    assert isinstance(stateless_input, dict)
    stateless_input["periods"] = [{"type": "1Y"}, {"type": "3Y"}]

    response = client.post("/analytics/risk/calculate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert set(body["results"]) == {"1Y", "3Y"}
    assert body["results"]["1Y"]["metrics"]["VOLATILITY"]["value"] is not None
    assert body["results"]["3Y"]["metrics"]["VAR"]["value"] is not None


def test_e2e_risk_calculate_stateful_mode() -> None:
    performance_client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
        )
    )
    with override_app_runtime(lotus_performance_client=performance_client):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/calculate",
            headers={"X-Correlation-Id": "corr-e2e-risk-stateful"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "metrics": ["VOLATILITY"],
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["results"]["YTD"]["metrics"]["VOLATILITY"]["value"] is not None
    assert performance_client.calls[0]["correlation_id"] == "corr-e2e-risk-stateful"


def test_e2e_risk_calculate_invalid_period_contract() -> None:
    client = TestClient(app)
    payload = _risk_payload()
    stateless_input = payload["stateless_input"]
    assert isinstance(stateless_input, dict)
    stateless_input["periods"] = [{"type": "EXPLICIT", "name": "Bad"}]
    response = client.post("/analytics/risk/calculate", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_e2e_drawdown_stateless_happy_path() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/drawdown", json=_drawdown_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateless"
    assert "YTD" in body["results"]
    assert body["results"]["YTD"]["summary"]["max_drawdown"] is not None


def test_e2e_drawdown_average_drawdown_public_contract() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/drawdown",
        json={
            "input_mode": "stateless",
            "stateless_input": {
                "scope": {"as_of_date": "2026-01-07", "net_or_gross": "NET"},
                "periods": [{"type": "YTD", "name": "YTD"}],
                "returns": [
                    {"date": "2026-01-02", "value": 5.0},
                    {"date": "2026-01-05", "value": -10.0},
                    {"date": "2026-01-06", "value": 2.0},
                    {"date": "2026-01-07", "value": 4.0},
                ],
            },
            "analysis_options": {"include_underwater_series": True},
        },
    )

    assert response.status_code == 200
    period = response.json()["results"]["YTD"]
    assert period["summary"]["average_drawdown"] == pytest.approx(-0.07576)
    assert period["summary"]["time_under_water_days"] == 3
    assert period["underwater_series"][1]["drawdown"] == pytest.approx(-0.1)
    assert period["underwater_series"][3]["drawdown"] == pytest.approx(-0.04528)


def test_e2e_rolling_metrics_stateless_happy_path() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/rolling-metrics", json=_rolling_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateless"
    assert "YTD" in body["results"]
    assert body["results"]["YTD"]["window_results"][0]["window_length"] == 3


def test_e2e_rolling_active_risk_metrics_follow_methodology_contract() -> None:
    client = TestClient(app)
    payload = _rolling_payload()
    stateless_input = payload["stateless_input"]
    assert isinstance(stateless_input, dict)
    rolling_options = stateless_input["rolling_options"]
    assert isinstance(rolling_options, dict)
    rolling_options["metrics"] = ["ROLLING_TRACKING_ERROR", "ROLLING_INFORMATION_RATIO"]
    rolling_options["annualization_basis"] = 252
    rolling_options["include_time_series"] = True

    response = client.post("/analytics/risk/rolling-metrics", json=payload)

    assert response.status_code == 200
    body = response.json()
    period = body["results"]["YTD"]
    assert period["benchmark_context"]["reason"] == "APPLIED"
    assert period["quality_flags"] == []

    window = period["window_results"][0]
    summaries = window["metric_summaries"]
    assert summaries["ROLLING_TRACKING_ERROR"]["latest"] == pytest.approx(0.23384610323886096)
    assert summaries["ROLLING_INFORMATION_RATIO"]["latest"] == pytest.approx(10.776318121606494)

    latest_point = window["metric_series"][-1]
    assert latest_point["metric_values"]["ROLLING_TRACKING_ERROR"] == pytest.approx(
        summaries["ROLLING_TRACKING_ERROR"]["latest"]
    )
    assert latest_point["metric_values"]["ROLLING_INFORMATION_RATIO"] == pytest.approx(
        summaries["ROLLING_INFORMATION_RATIO"]["latest"]
    )


def test_e2e_historical_attribution_stateless_happy_path() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/historical-attribution",
        json=_historical_attribution_payload(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateless"
    assert "YTD" in body["results"]


def test_e2e_historical_attribution_preserves_reconciliation_fields() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/historical-attribution",
        json=_historical_attribution_payload(),
    )
    assert response.status_code == 200

    body = response.json()
    attribution_sets = body["results"]["YTD"]["attribution_sets"]
    assert attribution_sets
    for attribution_set in attribution_sets:
        assert "total_value" in attribution_set
        assert "reconciled_sum" in attribution_set
        assert "residual" in attribution_set
        assert "contributors" in attribution_set


def test_e2e_concentration_stateless_payload() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/concentration",
        json={
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
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateless"
    assert body["risk_proxy"]["hhi_proposed"] == 6250.0


def test_e2e_concentration_stateful_mode() -> None:
    with override_app_runtime(
        lotus_core_client=SimulationLotusCoreClient(
            session_id="SIM_E2E_0001",
            simulation_version=2,
            include_ultimate_parent_issuer_id=True,
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
    assert body["metadata"]["portfolio_id"] == "DEMO_DPM_EUR_001"
    assert body["risk_proxy"]["hhi_current"] == 6800.0


def test_e2e_concentration_simulation_mode() -> None:
    with override_app_runtime(
        lotus_core_client=SimulationLotusCoreClient(
            session_id="SIM_E2E_0001",
            simulation_version=2,
            include_ultimate_parent_issuer_id=True,
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
    assert body["metadata"]["simulation_session_id"] == "SIM_E2E_0001"
    assert body["metadata"]["simulation_session_version"] == 2


def test_e2e_rolling_metrics_stateful_mode() -> None:
    with override_app_runtime(
        lotus_performance_client=RecordingLotusPerformanceClient(
            response_payload=build_returns_series_response(
                portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
                benchmark_returns=JAN_2026_ROLLING_BENCHMARK_RETURNS,
                risk_free_returns=JAN_2026_RISK_FREE_RETURNS,
            )
        ),
        lotus_core_client=SimulationLotusCoreClient(
            session_id="SIM_E2E_0001",
            simulation_version=2,
            include_ultimate_parent_issuer_id=True,
        ),
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/rolling-metrics",
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "rolling_options": {
                        "window_lengths": [2],
                        "metrics": [
                            "ROLLING_VOLATILITY",
                            "ROLLING_BETA",
                            "ROLLING_SHARPE",
                        ],
                    },
                },
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateful"
    assert "YTD" in body["results"]


def test_e2e_drawdown_stateful_mode_with_benchmark() -> None:
    performance_client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
            benchmark_returns=JAN_2026_DRAWDOWN_BENCHMARK_RETURNS,
        )
    )
    with override_app_runtime(lotus_performance_client=performance_client):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/drawdown",
            headers={"X-Correlation-Id": "corr-e2e-dd-stateful"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "benchmark_policy": {
                        "include_benchmark": True,
                        "missing_benchmark_policy": "REQUIRE",
                    },
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["input_mode"] == "stateful"
    assert performance_client.calls[0]["request_payload"]["series_selection"] == {
        "include_portfolio": True,
        "include_benchmark": True,
        "include_risk_free": False,
    }


def test_e2e_historical_attribution_stateful_active_risk_mode() -> None:
    performance_client = build_stateful_attribution_returns_client()
    core_client = RecordingHistoricalAttributionCoreClient()

    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-e2e-attr-active"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["ACTIVE_RISK"],
                        "metrics": ["TRACKING_ERROR"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateful"
    attribution_set = body["results"]["YTD"]["attribution_sets"][0]
    assert attribution_set["attribution_type"] == "ACTIVE_RISK"
    assert attribution_set["contributors"]
    assert performance_client.benchmark_exposure_context_calls
    assert not hasattr(core_client, "get_benchmark_market_series")


def test_e2e_historical_attribution_stateful_issuer_active_risk_mode() -> None:
    performance_client = build_stateful_attribution_returns_client()
    performance_client.benchmark_exposure_context_payload = (
        build_benchmark_exposure_context_response(grouping_dimension="ISSUER")
    )

    class _IssuerCoreClient(RecordingHistoricalAttributionCoreClient):
        async def get_instrument_enrichment(
            self,
            *,
            security_ids: list[str],
            correlation_id: str | None,  # noqa: ARG002
        ) -> dict[str, object]:
            return {
                "records": [
                    {"security_id": "SEC_A", "issuer_id": "ISSUER_A", "issuer_name": "Issuer A"},
                    {"security_id": "SEC_B", "issuer_id": "ISSUER_B", "issuer_name": "Issuer B"},
                ]
            }

    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=_IssuerCoreClient(),
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["ACTIVE_RISK"],
                        "metrics": ["TRACKING_ERROR"],
                        "grouping_dimensions": ["ISSUER"],
                    },
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["requested_grouping_dimensions"] == ["ISSUER"]
    assert body["metadata"]["stateful_active_risk_gated_grouping_dimensions"] == []
