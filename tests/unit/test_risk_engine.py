from src.app.contracts.risk import RiskCalculationRequest
from src.app.services.risk_engine import calculate_risk


def _base_payload() -> dict:
    return {
        "scope": {"asOfDate": "2025-03-31", "netOrGross": "NET"},
        "portfolioOpenDate": "2024-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "metrics": ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO", "DRAWDOWN"],
        "returns": [
            {"date": "2025-01-02", "value": 1.0},
            {"date": "2025-01-03", "value": 2.0},
            {"date": "2025-01-06", "value": -1.0},
            {"date": "2025-01-07", "value": 0.5},
        ],
        "benchmarkReturns": [
            {"date": "2025-01-02", "value": 0.8},
            {"date": "2025-01-03", "value": 1.1},
            {"date": "2025-01-06", "value": -0.7},
            {"date": "2025-01-07", "value": 0.4},
        ],
    }


def test_calculate_risk_benchmark_metrics() -> None:
    request = RiskCalculationRequest.model_validate(_base_payload())
    response = calculate_risk(request)
    ytd = response.results["YTD"].metrics
    assert ytd["BETA"].value is not None
    assert ytd["TRACKING_ERROR"].value is not None
    assert ytd["INFORMATION_RATIO"].value is not None
    assert ytd["DRAWDOWN"].details is not None


def test_calculate_risk_empty_returns() -> None:
    payload = _base_payload()
    payload["returns"] = []
    request = RiskCalculationRequest.model_validate(payload)
    response = calculate_risk(request)
    assert response.results == {}
