from app.contracts.risk import RiskCalculationRequest, RiskRequestPeriod
from app.services.risk_engine import calculate_risk


from typing import Any


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
