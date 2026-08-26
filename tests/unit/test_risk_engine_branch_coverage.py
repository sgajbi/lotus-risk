from datetime import date
from typing import Any, cast

import pandas as pd
import pytest
from pydantic import ValidationError

from app.contracts.risk import RiskCalculationRequest, RiskRequestPeriod
from app.main import app
from app.services import risk_engine
from app.services.risk import helpers as risk_helpers


def _payload_all_metrics() -> dict[str, object]:
    return {
        "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
        "portfolio_open_date": "2024-01-01",
        "periods": [
            {"type": "MTD", "name": "MTD"},
            {"type": "QTD", "name": "QTD"},
            {"type": "YTD", "name": "YTD"},
            {"type": "1Y", "name": "1Y"},
            {"type": "3Y", "name": "3Y"},
            {"type": "5Y", "name": "5Y"},
            {"type": "SI", "name": "SI"},
            {"type": "YEAR", "name": "Y2025", "year": 2025},
            {
                "type": "EXPLICIT",
                "name": "EXP",
                "from_date": "2025-01-01",
                "to_date": "2025-03-31",
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
            "use_log_returns": True,
            "risk_free_mode": "ANNUAL_RATE",
            "risk_free_annual_rate": 0.02,
            "mar_annual_rate": 0.01,
            "var": {"method": "GAUSSIAN", "confidence": 0.95, "horizon_days": 5},
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
        "benchmark_returns": [
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
    assert response.metadata.calculation_supportability.state == "stale"
    assert response.metadata.calculation_supportability.reason == "stale_source_observations"
    assert response.metadata.calculation_supportability.freshness_bucket == "stale"
    assert response.metadata.calculation_supportability.degraded_metric_count == 0


def test_var_helper_unsupported_method_raises() -> None:
    series = pd.Series([0.1, -0.1, 0.2, -0.05])
    with pytest.raises(ValueError, match="Unsupported VaR method"):
        risk_helpers._calculate_var_by_method(series, "INVALID", 0.95)


def test_resolve_period_rejects_invalid_type() -> None:
    with pytest.raises(ValueError, match="Unsupported period type"):
        risk_helpers._resolve_period("BAD", date(2025, 3, 31), date(2024, 1, 1))


def test_resample_and_log_helpers_cover_empty_and_weekly() -> None:
    empty = pd.Series(dtype=float)
    assert risk_helpers._resample_returns(empty, "DAILY").empty
    weekly_input = pd.Series(
        [1.0, 2.0, -1.0],
        index=pd.to_datetime(["2025-01-06", "2025-01-07", "2025-01-10"]),
    )
    weekly = risk_helpers._resample_returns(weekly_input, "WEEKLY")
    assert not weekly.empty
    assert not risk_helpers._to_log_returns(weekly).empty


def test_drawdown_empty_series_and_require_data_error() -> None:
    empty = pd.Series(dtype=float)
    details = risk_helpers._drawdown(empty)
    assert details["peak_date"] is None
    with pytest.raises(ValueError, match="Insufficient data"):
        risk_helpers._require_data(empty)


def test_endpoint_error_path_returns_400() -> None:
    import app.routers.risk_calculation as risk_calculation_module

    risk_calculation_module_any = cast(Any, risk_calculation_module)
    original = risk_calculation_module_any.calculate_risk

    def _raise(_request: object) -> None:
        raise ValueError("forced")

    risk_calculation_module_any.calculate_risk = _raise
    try:
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post(
            "/analytics/risk/calculate",
            json={
                "input_mode": "stateless",
                "stateless_input": {
                    "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
                    "portfolio_open_date": "2024-01-01",
                    "periods": [{"type": "YTD"}],
                    "metrics": ["VOLATILITY"],
                    "returns": [{"date": "2025-01-01", "value": 0.1}],
                },
            },
            headers={"X-Correlation-Id": "corr-400"},
        )
        assert response.status_code == 400
        body = response.json()["error"]
        assert body["code"] == "INVALID_INPUT"
        assert body["correlation_id"] == "corr-400"
    finally:
        risk_calculation_module_any.calculate_risk = original


def test_health_ready_draining_branch() -> None:
    from fastapi.testclient import TestClient

    app.state.is_draining = True
    client = TestClient(app)
    response = client.get("/health/ready")
    ops_response = client.get("/ops")
    assert response.status_code == 503
    assert ops_response.status_code == 200
    assert ops_response.json()["status"] == "degraded"
    assert ops_response.json()["checks"]["ready"] is False
    app.state.is_draining = False


def test_period_year_requires_year_validation() -> None:
    with pytest.raises(ValidationError):
        RiskRequestPeriod.model_validate({"type": "YEAR"})


def test_resolve_period_validates_required_inputs() -> None:
    with pytest.raises(ValueError, match="EXPLICIT period requires"):
        risk_helpers._resolve_period("EXPLICIT", date(2025, 3, 31), date(2024, 1, 1))
    with pytest.raises(ValueError, match="YEAR period requires year"):
        risk_helpers._resolve_period("YEAR", date(2025, 3, 31), date(2024, 1, 1))


def test_to_log_returns_empty_series_passthrough() -> None:
    empty = pd.Series(dtype=float)
    assert risk_helpers._to_log_returns(empty).empty


def test_to_log_returns_rejects_undefined_values() -> None:
    returns = pd.Series([-100.0, 1.0], index=pd.to_datetime(["2026-01-01", "2026-01-02"]))

    with pytest.raises(ValueError, match="Log returns are undefined"):
        risk_helpers._to_log_returns(returns)


def test_risk_metrics_return_domain_errors_for_insufficient_data() -> None:
    payload = {
        "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
        "portfolio_open_date": "2024-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
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
        "returns": [{"date": "2025-01-02", "value": 0.5}],
        "benchmark_returns": [{"date": "2025-01-02", "value": 0.4}],
    }
    response = risk_engine.calculate_risk(RiskCalculationRequest.model_validate(payload))
    supportability = response.metadata.calculation_supportability
    assert supportability.state == "degraded"
    assert supportability.reason == "insufficient_aligned_observations"
    assert supportability.degraded_metric_count == len(cast(list[str], payload["metrics"])) - 1
    metrics = response.results["YTD"].metrics
    metric_names = cast(list[str], payload["metrics"])
    benchmark_aligned_metrics = {"BETA", "TRACKING_ERROR", "INFORMATION_RATIO"}
    for metric_name in metric_names:
        metric = metrics[metric_name]
        if metric_name == "DRAWDOWN":
            assert metric.value == 0.0
        else:
            assert metric.value is None
        assert metric.details is not None
        if metric_name in benchmark_aligned_metrics:
            expected_error = "Insufficient aligned observations"
        elif metric_name == "DRAWDOWN":
            expected_error = None
        else:
            expected_error = "Insufficient data"
        if expected_error is not None:
            assert metric.details["error"] == expected_error


def test_benchmark_metrics_report_zero_benchmark_variance_as_domain_error() -> None:
    payload = {
        "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
        "portfolio_open_date": "2024-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "metrics": ["BETA"],
        "returns": [
            {"date": "2025-01-02", "value": 0.5},
            {"date": "2025-01-03", "value": 0.7},
        ],
        "benchmark_returns": [
            {"date": "2025-01-02", "value": 0.4},
            {"date": "2025-01-03", "value": 0.4},
        ],
    }

    response = risk_engine.calculate_risk(RiskCalculationRequest.model_validate(payload))

    beta = response.results["YTD"].metrics["BETA"]
    assert beta.value is None
    assert beta.details == {"error": "Benchmark variance is zero"}


def test_risk_calculation_supportability_reports_empty_when_no_returns() -> None:
    payload = {
        "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
        "portfolio_open_date": "2024-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "metrics": ["VOLATILITY"],
        "returns": [],
    }

    response = risk_engine.calculate_risk(RiskCalculationRequest.model_validate(payload))

    assert response.results == {}
    supportability = response.metadata.calculation_supportability
    assert supportability.state == "empty"
    assert supportability.reason == "no_return_observations"
    assert supportability.freshness_bucket == "unknown"


def test_risk_calculation_supportability_reports_stale_source_observations() -> None:
    payload = {
        "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
        "portfolio_open_date": "2024-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "metrics": ["VOLATILITY"],
        "returns": [
            {"date": "2025-01-02", "value": 0.5},
            {"date": "2025-01-03", "value": -0.2},
        ],
    }

    response = risk_engine.calculate_risk(RiskCalculationRequest.model_validate(payload))

    supportability = response.metadata.calculation_supportability
    assert supportability.state == "stale"
    assert supportability.reason == "stale_source_observations"
    assert supportability.freshness_bucket == "stale"


def test_beta_and_information_ratio_guard_clauses() -> None:
    constant = pd.Series([0.2, 0.2, 0.2])
    with pytest.raises(ValueError, match="Benchmark variance is zero"):
        risk_helpers._beta(pd.Series([0.1, 0.3, 0.2]), constant)
    with pytest.raises(ValueError, match="Tracking error is zero"):
        risk_helpers._information_ratio(constant, constant, annual_factor=252)


def test_benchmark_metric_dispatch_rejects_unknown_metric() -> None:
    with pytest.raises(ValueError, match="Unsupported benchmark metric"):
        risk_helpers._calculate_benchmark_metric(
            "UNKNOWN",
            pd.Series([0.1, 0.2]),
            pd.Series([0.1, 0.2]),
            annual_factor=252,
        )


def test_sharpe_and_sortino_error_contracts() -> None:
    zero_vol_payload = {
        "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
        "portfolio_open_date": "2024-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "metrics": ["SHARPE"],
        "returns": [
            {"date": "2025-01-02", "value": 0.5},
            {"date": "2025-01-03", "value": 0.5},
        ],
    }
    sharpe_response = risk_engine.calculate_risk(
        RiskCalculationRequest.model_validate(zero_vol_payload)
    )
    sharpe_error = sharpe_response.results["YTD"].metrics["SHARPE"].details
    assert sharpe_error is not None
    assert sharpe_error["error"] == "Zero volatility"

    no_downside_payload = {
        "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
        "portfolio_open_date": "2024-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "metrics": ["SORTINO"],
        "returns": [
            {"date": "2025-01-02", "value": 1.0},
            {"date": "2025-01-03", "value": 2.0},
        ],
    }
    sortino_response = risk_engine.calculate_risk(
        RiskCalculationRequest.model_validate(no_downside_payload)
    )
    sortino_error = sortino_response.results["YTD"].metrics["SORTINO"].details
    assert sortino_error is not None
    assert sortino_error["error"] == "No downside observations"
