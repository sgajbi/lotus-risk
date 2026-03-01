from fastapi.testclient import TestClient

from app.main import app


def _stateless_payload() -> dict[str, object]:
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
                "metrics": [
                    "ROLLING_VOLATILITY",
                    "ROLLING_SHARPE",
                    "ROLLING_BETA",
                    "ROLLING_TRACKING_ERROR",
                    "ROLLING_INFORMATION_RATIO",
                    "ROLLING_MAX_DRAWDOWN",
                ],
                "include_time_series": True,
            },
        },
    }


def test_rolling_metrics_endpoint_stateless_contract() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/rolling-metrics", json=_stateless_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source_service"] == "lotus-risk"
    assert body["input_mode"] == "stateless"
    assert body["metadata"]["methodology_version"] == "rolling_metrics.v1"
    assert "YTD" in body["results"]
    window = body["results"]["YTD"]["window_results"][0]
    assert window["window_length"] == 3
    assert "ROLLING_VOLATILITY" in window["metric_summaries"]


def test_rolling_metrics_endpoint_rejects_stateful_mode_for_now() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/rolling-metrics",
        json={
            "input_mode": "stateful",
            "stateful_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-08",
                "periods": [{"type": "YTD"}],
            },
        },
    )
    assert response.status_code == 400
    assert "not implemented" in response.json()["error"]["message"]


def test_rolling_metrics_endpoint_rejects_simulation_mode_for_now() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/rolling-metrics",
        json={
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-08",
                "periods": [{"type": "YTD"}],
            },
        },
    )
    assert response.status_code == 400
    assert "not implemented" in response.json()["error"]["message"]
