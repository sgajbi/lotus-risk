from fastapi.testclient import TestClient
from app.main import app


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


class _FakeLotusCoreClient:
    async def create_simulation_session(
        self,
        *,
        portfolio_id: str,
        ttl_hours: int | None,
        created_by: str | None,
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {
            "session": {
                "session_id": "SIM_E2E_0001",
                "portfolio_id": portfolio_id,
                "status": "ACTIVE",
                "version": 1,
                "created_by": created_by,
                "created_at": "2026-02-27T10:30:00Z",
                "expires_at": "2026-02-28T10:30:00Z",
            }
        }

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, object]],
        correlation_id: str | None,
    ) -> dict[str, object]:
        assert session_id == "SIM_E2E_0001"
        assert len(changes) == 1
        return {"session_id": session_id, "version": 2, "changes": []}

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        if request_payload.get("snapshot_mode") == "BASELINE":
            return {
                "portfolio_id": portfolio_id,
                "as_of_date": "2026-02-27",
                "snapshot_mode": "BASELINE",
                "valuation_context": {
                    "portfolio_currency": "EUR",
                    "reporting_currency": "USD",
                    "position_basis": "market_value_base",
                    "weight_basis": "total_market_value_base",
                },
                "sections": {
                    "positions_baseline": [
                        {"security_id": "SEC_A", "market_value_base": "80"},
                        {"security_id": "SEC_B", "market_value_base": "20"},
                    ]
                },
            }
        return {
            "portfolio_id": portfolio_id,
            "as_of_date": "2026-02-27",
            "snapshot_mode": "SIMULATION",
            "valuation_context": {
                "portfolio_currency": "EUR",
                "reporting_currency": "USD",
                "position_basis": "market_value_base",
                "weight_basis": "total_market_value_base",
            },
            "simulation": {
                "session_id": "SIM_E2E_0001",
                "version": 2,
                "baseline_as_of_date": "2026-02-27",
            },
            "sections": {
                "positions_baseline": [
                    {"security_id": "SEC_A", "market_value_base": "60"},
                    {"security_id": "SEC_B", "market_value_base": "40"},
                ],
                "positions_projected": [
                    {"security_id": "SEC_A", "market_value_base": "90"},
                    {"security_id": "SEC_B", "market_value_base": "10"},
                ],
            },
        }

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {
            "records": [
                {
                    "security_id": security_id,
                    "issuer_id": f"ISSUER_{security_id}",
                    "ultimate_parent_issuer_id": f"UPI_{security_id}",
                }
                for security_id in security_ids
            ]
        }


class _FakeLotusPerformanceClient:
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        assert request_payload["input_mode"] == "stateful"
        assert request_payload["stateful_input"] == {"consumer_system": "lotus-risk"}
        return {
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "0.0100"},
                    {"date": "2026-01-03", "return_value": "-0.0200"},
                    {"date": "2026-01-04", "return_value": "0.0050"},
                ],
                "benchmark_returns": [
                    {"date": "2026-01-02", "return_value": "0.0080"},
                    {"date": "2026-01-03", "return_value": "-0.0150"},
                    {"date": "2026-01-04", "return_value": "0.0040"},
                ],
                "risk_free_returns": [
                    {"date": "2026-01-02", "return_value": "0.0001"},
                    {"date": "2026-01-03", "return_value": "0.0001"},
                    {"date": "2026-01-04", "return_value": "0.0001"},
                ],
            }
        }


def test_e2e_concentration_stateful_mode() -> None:
    client = TestClient(app)
    app.state.lotus_core_client = _FakeLotusCoreClient()
    response = client.post(
        "/analytics/risk/concentration",
        json={
            "input_mode": "stateful",
            "stateful_input": {"portfolio_id": "DEMO_DPM_EUR_001", "as_of_date": "2026-02-27"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateful"
    assert body["metadata"]["portfolio_id"] == "DEMO_DPM_EUR_001"
    assert body["risk_proxy"]["hhi_current"] == 6800.0


def test_e2e_concentration_simulation_mode() -> None:
    client = TestClient(app)
    app.state.lotus_core_client = _FakeLotusCoreClient()
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
    client = TestClient(app)
    app.state.lotus_performance_client = _FakeLotusPerformanceClient()
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
