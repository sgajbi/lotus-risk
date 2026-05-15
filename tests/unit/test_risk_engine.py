from typing import Any

import pytest

from app.contracts.risk import RiskCalculationRequest, RiskRequestPeriod
from app.services.risk_engine import calculate_risk


def _base_payload() -> dict[str, Any]:
    return {
        "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
        "portfolio_open_date": "2024-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "metrics": ["VOLATILITY", "SHARPE", "VAR"],
        "options": {
            "frequency": "DAILY",
            "risk_free_mode": "ANNUAL_RATE",
            "risk_free_annual_rate": 0.01,
            "var": {"confidence": 0.95, "horizon_days": 1, "include_expected_shortfall": True},
        },
        "returns": [
            {"date": "2025-01-02", "value": 1.0},
            {"date": "2025-01-03", "value": 2.0},
            {"date": "2025-01-06", "value": -1.0},
            {"date": "2025-01-07", "value": 0.5},
        ],
    }


def test_period_explicit_canonical_fields() -> None:
    period = RiskRequestPeriod.model_validate(
        {
            "type": "EXPLICIT",
            "from_date": "2025-01-01",
            "to_date": "2025-01-31",
            "name": "Explicit",
        }
    )
    assert period.type == "EXPLICIT"
    assert str(period.from_date) == "2025-01-01"
    assert str(period.to_date) == "2025-01-31"


def test_period_accepts_canonical_trailing_year_type() -> None:
    period = RiskRequestPeriod.model_validate({"type": "1Y"})

    assert period.type == "1Y"


def test_period_normalizes_legacy_trailing_year_alias_type() -> None:
    period = RiskRequestPeriod.model_validate({"type": "THREE_YEAR"})

    assert period.type == "3Y"


def test_period_validation_rejects_missing_explicit_bounds() -> None:
    try:
        RiskRequestPeriod.model_validate({"type": "EXPLICIT"})
        assert False, "Expected validation error"
    except Exception as exc:  # pydantic validation type is enough here
        assert "EXPLICIT period requires" in str(exc)


def test_calculate_risk_var_methods() -> None:
    payload = _base_payload()
    methods = ["HISTORICAL", "GAUSSIAN", "CORNISH_FISHER"]
    results = []
    for method in methods:
        payload["options"]["var"]["method"] = method
        request = RiskCalculationRequest.model_validate(payload)
        response = calculate_risk(request)
        var_value = response.results["YTD"].metrics["VAR"].value
        assert var_value is not None
        results.append(var_value)

    assert len(set(results)) >= 2


def test_volatility_matches_documented_percentage_point_output_contract() -> None:
    payload = {
        "scope": {"as_of_date": "2026-01-03", "net_or_gross": "NET"},
        "portfolio_open_date": "2026-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "metrics": ["VOLATILITY"],
        "options": {
            "frequency": "DAILY",
            "use_log_returns": False,
        },
        "returns": [
            {"date": "2026-01-01", "value": 1.00},
            {"date": "2026-01-02", "value": -0.50},
            {"date": "2026-01-03", "value": 0.20},
        ],
    }

    response = calculate_risk(RiskCalculationRequest.model_validate(payload))

    metric = response.results["YTD"].metrics["VOLATILITY"]
    assert metric.value == pytest.approx(11.914696806885186)
    assert metric.details is not None
    assert metric.details["standard_deviation"] == pytest.approx(0.007505553499465135)
    assert metric.details["observation_count"] == 3
    assert metric.details["annualization_factor"] == 252


def test_sharpe_matches_documented_dimensionless_output_contract() -> None:
    payload = {
        "scope": {"as_of_date": "2026-01-03", "net_or_gross": "NET"},
        "portfolio_open_date": "2026-01-01",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "metrics": ["SHARPE"],
        "options": {
            "frequency": "DAILY",
            "use_log_returns": False,
            "risk_free_mode": "ANNUAL_RATE",
            "risk_free_annual_rate": 0.02,
        },
        "returns": [
            {"date": "2026-01-01", "value": 1.00},
            {"date": "2026-01-02", "value": -0.50},
            {"date": "2026-01-03", "value": 0.20},
        ],
    }

    response = calculate_risk(RiskCalculationRequest.model_validate(payload))

    metric = response.results["YTD"].metrics["SHARPE"]
    assert metric.value == pytest.approx(4.768871619893194)
    assert metric.details is not None
    assert metric.details["mean_return"] == pytest.approx(0.002333333333333333)
    assert metric.details["periodic_risk_free_rate"] == pytest.approx(0.0000785849419846496)
    assert metric.details["excess_return"] == pytest.approx(0.0022547483913486835)
    assert metric.details["annualized_excess_return"] == pytest.approx(0.5681965946198683)
    assert metric.details["volatility"] == pytest.approx(0.007505553499465135)
    assert metric.details["observation_count"] == 3
    assert metric.details["annualization_factor"] == 252


def test_drawdown_metadata_fields_present() -> None:
    payload = _base_payload()
    payload["metrics"] = ["DRAWDOWN"]
    request = RiskCalculationRequest.model_validate(payload)
    response = calculate_risk(request)
    details = response.results["YTD"].metrics["DRAWDOWN"].details
    assert details is not None
    assert "max_drawdown" in details
    assert "peak_date" in details
    assert "trough_date" in details
    assert "max_drawdown_date" in details


def test_benchmark_metrics_require_benchmark_series() -> None:
    payload = _base_payload()
    payload["metrics"] = ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"]
    payload["benchmark_returns"] = []

    response = calculate_risk(RiskCalculationRequest.model_validate(payload))
    metrics = response.results["YTD"].metrics
    for metric_name in ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"]:
        assert metric_name in metrics
        assert metrics[metric_name].value is None
        details = metrics[metric_name].details
        assert details is not None
        assert "Benchmark returns required" in str(details.get("error"))


def test_calculate_risk_empty_returns() -> None:
    payload = _base_payload()
    payload["returns"] = []
    request = RiskCalculationRequest.model_validate(payload)
    response = calculate_risk(request)
    assert response.results == {}
