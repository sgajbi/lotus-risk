from fastapi.testclient import TestClient

from app.main import app
from tests.support.app_runtime import override_app_runtime
from tests.support.returns_series_payloads import build_returns_series_response


def _stateless_attribution_payload() -> dict[str, object]:
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
                    "group_label": "Technology",
                    "weight": 0.55,
                },
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.45,
                },
                {
                    "date": "2026-01-03",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-03",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-04",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.52,
                },
                {
                    "date": "2026-01-04",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.48,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.54,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.46,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.53,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.47,
                },
            ],
            "benchmark_exposure_history": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.48,
                },
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.52,
                },
                {
                    "date": "2026-01-03",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.47,
                },
                {
                    "date": "2026-01-03",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.53,
                },
                {
                    "date": "2026-01-04",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.49,
                },
                {
                    "date": "2026-01-04",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.51,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.49,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.51,
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


def test_historical_attribution_stateless_happy_path() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/historical-attribution",
        json=_stateless_attribution_payload(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_service"] == "lotus-risk"
    assert body["input_mode"] == "stateless"
    assert "YTD" in body["results"]
    ytd = body["results"]["YTD"]
    assert ytd["error"] is None
    assert len(ytd["attribution_sets"]) == 4


def test_historical_attribution_stateful_total_risk_happy_path() -> None:
    class _FakeLotusPerformanceClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object | None]] = []

        async def get_returns_series(
            self,
            *,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            self.calls.append(
                {
                    "request_payload": request_payload,
                    "correlation_id": correlation_id,
                }
            )
            return build_returns_series_response(
                portfolio_returns=[
                    ("2026-01-02", "0.0100"),
                    ("2026-01-03", "-0.0050"),
                    ("2026-01-04", "0.0040"),
                ]
            )

    class _FakeLotusCoreClient:
        def __init__(self) -> None:
            self.position_calls: list[dict[str, object | None]] = []

        async def get_position_analytics_timeseries(
            self,
            *,
            portfolio_id: str,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            self.position_calls.append(
                {
                    "portfolio_id": portfolio_id,
                    "request_payload": request_payload,
                    "correlation_id": correlation_id,
                }
            )
            return {
                "rows": [
                    {
                        "security_id": "SEC_A",
                        "valuation_date": "2026-01-02",
                        "dimensions": {"sector": "TECH", "asset_class": "EQUITY"},
                        "ending_market_value_portfolio_currency": "60",
                    },
                    {
                        "security_id": "SEC_B",
                        "valuation_date": "2026-01-02",
                        "dimensions": {"sector": "HEALTH", "asset_class": "EQUITY"},
                        "ending_market_value_portfolio_currency": "40",
                    },
                    {
                        "security_id": "SEC_A",
                        "valuation_date": "2026-01-03",
                        "dimensions": {"sector": "TECH", "asset_class": "EQUITY"},
                        "ending_market_value_portfolio_currency": "65",
                    },
                    {
                        "security_id": "SEC_B",
                        "valuation_date": "2026-01-03",
                        "dimensions": {"sector": "HEALTH", "asset_class": "EQUITY"},
                        "ending_market_value_portfolio_currency": "35",
                    },
                ],
                "page": {"next_page_token": None},
            }

        async def get_instrument_enrichment(
            self,
            *,
            security_ids: list[str],
            correlation_id: str | None,
        ) -> dict[str, object]:
            return {"records": []}

    performance_client = _FakeLotusPerformanceClient()
    core_client = _FakeLotusCoreClient()
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-stateful"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-04",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["TOTAL_RISK"],
                        "metrics": ["VOLATILITY"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateful"
    assert body["results"]["YTD"]["error"] is None
    assert performance_client.calls == [
        {
            "request_payload": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-04",
                "input_mode": "stateful",
                "stateful_input": {},
                "metric_basis": "NET",
                "window": {
                    "mode": "EXPLICIT",
                    "from_date": "2026-01-01",
                    "to_date": "2026-01-04",
                },
                "frequency": "DAILY",
                "reporting_currency": None,
                "series_selection": {
                    "include_portfolio": True,
                    "include_benchmark": False,
                    "include_risk_free": False,
                },
                "data_policy": {
                    "missing_data_policy": "ALLOW_PARTIAL",
                    "fill_method": "NONE",
                    "calendar_policy": "BUSINESS",
                },
            },
            "correlation_id": "corr-attr-stateful",
        }
    ]
    assert core_client.position_calls == [
        {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "request_payload": {
                "as_of_date": "2026-01-04",
                "window": {
                    "start_date": "2026-01-02",
                    "end_date": "2026-01-04",
                },
                "frequency": "daily",
                "dimensions": ["sector"],
                "consumer_system": "lotus-risk",
                "page": {"page_size": 5000, "page_token": None},
            },
            "correlation_id": "corr-attr-stateful",
        }
    ]


def test_historical_attribution_stateful_rejects_active_risk_until_benchmark_exposure_contract() -> (
    None
):
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/historical-attribution",
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
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_INPUT"
    assert "benchmark exposure history contract" in error["message"]

