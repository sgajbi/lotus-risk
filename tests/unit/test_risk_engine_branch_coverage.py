from datetime import date
from typing import Any, cast

import pandas as pd
import pytest

from app.contracts.risk import RiskCalculationRequest, RiskRequestPeriod
from app.main import app
from app.services import risk_engine


def _payload_all_metrics() -> dict[str, object]:
    return {
        "scope": {"asOfDate": "2025-03-31", "netOrGross": "NET"},
        "portfolioOpenDate": "2024-01-01",
        "periods": [
            {"type": "MTD", "name": "MTD"},
            {"type": "QTD", "name": "QTD"},
            {"type": "YTD", "name": "YTD"},
            {"type": "ONE_YEAR", "name": "1Y"},
            {"type": "THREE_YEAR", "name": "3Y"},
            {"type": "FIVE_YEAR", "name": "5Y"},
            {"type": "SI", "name": "SI"},
            {"type": "YEAR", "name": "Y2025", "year": 2025},
            {
                "type": "EXPLICIT",
                "name": "EXP",
                "fromDate": "2025-01-01",
                "toDate": "2025-03-31",
            },
        ],
        "metrics": [
            "VOLATILITY",
            "DRAWDOWN",
            "SHARPE",
            "SORTINO",
            "BETA",
            "TRACKING_ERROR",
            "INFORMATION_RATIO",
            "VAR",
        ],
        "options": {
            "frequency": "WEEKLY",
            "useLogReturns": True,
            "riskFreeMode": "ANNUAL_RATE",
            "riskFreeAnnualRate": 0.02,
            "marAnnualRate": 0.01,
            "var": {"method": "GAUSSIAN", "confidence": 0.95, "horizonDays": 5},
        },
        "returns": [
            {"date": "2024-12-30", "value": 0.3},
            {"date": "2025-01-03", "value": 0.8},
            {"date": "2025-01-10", "value": -0.4},
            {"date": "2025-01-17", "value": 0.5},
            {"date": "2025-01-24", "value": -0.2},
            {"date": "2025-01-31", "value": 0.6},
            {"date": "2025-02-07", "value": 0.4},
            {"date": "2025-02-14", "value": -0.3},
            {"date": "2025-02-21", "value": 0.7},
            {"date": "2025-02-28", "value": 0.2},
            {"date": "2025-03-07", "value": -0.5},
            {"date": "2025-03-14", "value": 0.9},
            {"date": "2025-03-21", "value": 0.1},
            {"date": "2025-03-28", "value": -0.2},
        ],
        "benchmarkReturns": [
            {"date": "2024-12-30", "value": 0.2},
            {"date": "2025-01-03", "value": 0.6},
            {"date": "2025-01-10", "value": -0.3},
            {"date": "2025-01-17", "value": 0.4},
            {"date": "2025-01-24", "value": -0.1},
            {"date": "2025-01-31", "value": 0.5},
            {"date": "2025-02-07", "value": 0.3},
            {"date": "2025-02-14", "value": -0.2},
            {"date": "2025-02-21", "value": 0.4},
            {"date": "2025-02-28", "value": 0.1},
            {"date": "2025-03-07", "value": -0.4},
            {"date": "2025-03-14", "value": 0.7},
            {"date": "2025-03-21", "value": 0.2},
            {"date": "2025-03-28", "value": -0.1},
        ],
    }


def test_engine_covers_all_period_types_and_benchmark_metrics() -> None:
    request = RiskCalculationRequest.model_validate(_payload_all_metrics())
    response = risk_engine.calculate_risk(request)
    assert "EXP" in response.results
    metrics = response.results["EXP"].metrics
    assert metrics["BETA"].value is not None
    assert metrics["TRACKING_ERROR"].value is not None
    assert metrics["INFORMATION_RATIO"].value is not None


def test_var_helper_unsupported_method_raises() -> None:
    series = pd.Series([0.1, -0.1, 0.2, -0.05])
    with pytest.raises(ValueError, match="Unsupported VaR method"):
        risk_engine._calculate_var_by_method(series, "INVALID", 0.95)


def test_resolve_period_rejects_invalid_type() -> None:
    with pytest.raises(ValueError, match="Unsupported period type"):
        risk_engine._resolve_period("BAD", date(2025, 3, 31), date(2024, 1, 1))


def test_resample_and_log_helpers_cover_empty_and_weekly() -> None:
    empty = pd.Series(dtype=float)
    assert risk_engine._resample_returns(empty, "DAILY").empty
    weekly_input = pd.Series(
        [1.0, 2.0, -1.0],
        index=pd.to_datetime(["2025-01-06", "2025-01-07", "2025-01-10"]),
    )
    weekly = risk_engine._resample_returns(weekly_input, "WEEKLY")
    assert not weekly.empty
    assert not risk_engine._to_log_returns(weekly).empty


def test_drawdown_empty_series_and_require_data_error() -> None:
    empty = pd.Series(dtype=float)
    details = risk_engine._drawdown(empty)
    assert details["peak_date"] is None
    with pytest.raises(ValueError, match="Insufficient data"):
        risk_engine._require_data(empty)


def test_endpoint_error_path_returns_400() -> None:
    import app.main as main_module

    main_module_any = cast(Any, main_module)
    original = main_module_any.calculate_risk

    def _raise(_request: object) -> None:
        raise ValueError("forced")

    main_module_any.calculate_risk = _raise
    try:
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post(
            "/analytics/risk/calculate",
            json={
                "scope": {"asOfDate": "2025-03-31", "netOrGross": "NET"},
                "portfolioOpenDate": "2024-01-01",
                "periods": [{"type": "YTD"}],
                "metrics": ["VOLATILITY"],
                "returns": [{"date": "2025-01-01", "value": 0.1}],
            },
        )
        assert response.status_code == 400
    finally:
        main_module_any.calculate_risk = original


def test_health_ready_draining_branch() -> None:
    from fastapi.testclient import TestClient

    app.state.is_draining = True
    client = TestClient(app)
    response = client.get("/health/ready")
    assert response.status_code == 503
    app.state.is_draining = False


def test_period_year_requires_year_validation() -> None:
    with pytest.raises(Exception):
        RiskRequestPeriod.model_validate({"type": "YEAR"})
