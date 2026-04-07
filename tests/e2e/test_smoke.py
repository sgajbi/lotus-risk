from fastapi.testclient import TestClient
from app.main import app
from tests.support.app_runtime import override_app_runtime
from tests.support.historical_attribution_fakes import (
    RecordingHistoricalAttributionCoreClient,
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
                {"date": "2026-01-03", "value": 0.8},
                {"date": "2026-01-04", "value": -0.4},
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
                {"date": "2026-01-03", "value": -2.0},
                {"date": "2026-01-04", "value": 0.5},
                {"date": "2026-01-05", "value": 1.2},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-03", "value": -1.5},
                {"date": "2026-01-04", "value": 0.4},
                {"date": "2026-01-05", "value": 1.0},
            ],
            "risk_free_returns": [
                {"date": "2026-01-02", "value": 0.01},
                {"date": "2026-01-03", "value": 0.01},
                {"date": "2026-01-04", "value": 0.01},
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
                {"date": "2026-01-03", "value": -0.4},
                {"date": "2026-01-04", "value": 0.3},
                {"date": "2026-01-05", "value": 0.6},
                {"date": "2026-01-06", "value": -0.2},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-03", "value": -0.3},
                {"date": "2026-01-04", "value": 0.2},
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
                    "date": "2026-01-03",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-03",
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
                    "date": "2026-01-03",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "weight": 0.47,
                },
                {
                    "date": "2026-01-03",
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


def test_e2e_risk_calculate_happy_path() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/calculate", json=_risk_payload())
    assert response.status_code == 200
    body = response.json()
    assert "YTD" in body["results"]
    metrics = body["results"]["YTD"]["metrics"]
    assert metrics["VOLATILITY"]["value"] is not None
    assert metrics["VAR"]["value"] is not None


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
                    "as_of_date": "2026-01-04",
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


def test_e2e_rolling_metrics_stateless_happy_path() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/rolling-metrics", json=_rolling_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateless"
    assert "YTD" in body["results"]
    assert body["results"]["YTD"]["window_results"][0]["window_length"] == 3


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
                    "as_of_date": "2026-01-04",
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
                    "as_of_date": "2026-01-04",
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
                    "as_of_date": "2026-01-04",
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
