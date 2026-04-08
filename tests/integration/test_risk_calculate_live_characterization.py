from __future__ import annotations

import os
from datetime import date

import httpx
import numpy as np
import pytest

from app.contracts.risk import RiskRequestPeriod
from app.services.stateful_returns_request import build_stateful_returns_series_request
from tests.support.live_returns_series import extract_decimal_returns, fetch_live_returns_series


def _live_enabled() -> bool:
    return os.getenv("LOTUS_RISK_RUN_LIVE_RISK") == "1"


pytestmark = pytest.mark.skipif(
    not _live_enabled(),
    reason="set LOTUS_RISK_RUN_LIVE_RISK=1 to run live risk reconciliation",
)


RISK_BASE_URL = os.getenv("LOTUS_RISK_BASE_URL", "http://localhost:8130")
PERFORMANCE_BASE_URL = os.getenv("LOTUS_PERFORMANCE_BASE_URL", "http://localhost:8002")
PORTFOLIO_ID = os.getenv("LOTUS_RISK_LIVE_PORTFOLIO_ID", "PB_SG_GLOBAL_BAL_001")
AS_OF_DATE = os.getenv("LOTUS_RISK_LIVE_AS_OF_DATE", "2026-03-31")
ANNUALIZATION_FACTOR = 252


def _annualized_volatility(returns: list[float]) -> float:
    return float(np.std(returns, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR) * 100.0)


def _beta(portfolio_returns: list[float], benchmark_returns: list[float]) -> float:
    covariance = np.cov(portfolio_returns, benchmark_returns, ddof=1)
    return float(covariance[0, 1] / covariance[1, 1])


def _tracking_error(portfolio_returns: list[float], benchmark_returns: list[float]) -> float:
    active_returns = np.array(portfolio_returns) - np.array(benchmark_returns)
    return float(np.std(active_returns, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR) * 100.0)


def _information_ratio(portfolio_returns: list[float], benchmark_returns: list[float]) -> float:
    active_returns = np.array(portfolio_returns) - np.array(benchmark_returns)
    return float(
        (np.mean(active_returns) / np.std(active_returns, ddof=1)) * np.sqrt(ANNUALIZATION_FACTOR)
    )


def test_live_stateful_risk_calculate_reconciles_selected_metrics() -> None:
    returns_payload = build_stateful_returns_series_request(
        portfolio_id=PORTFOLIO_ID,
        as_of_date=date.fromisoformat(AS_OF_DATE),
        periods=[RiskRequestPeriod(type="YTD", name="YTD")],
        frequency="DAILY",
        metric_basis="NET",
        reporting_currency=None,
        include_benchmark=True,
        include_risk_free=False,
        missing_data_policy="FAIL_FAST",
    )
    risk_payload = {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": PORTFOLIO_ID,
            "as_of_date": AS_OF_DATE,
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY", "BETA", "TRACKING_ERROR", "INFORMATION_RATIO"],
            "options": {"frequency": "DAILY"},
        },
    }

    upstream_body = fetch_live_returns_series(
        base_url=PERFORMANCE_BASE_URL,
        request_payload=returns_payload,
    )
    with httpx.Client(timeout=30.0) as client:
        risk_response = client.post(f"{RISK_BASE_URL}/analytics/risk/calculate", json=risk_payload)
        risk_response.raise_for_status()

    series = upstream_body["series"]
    portfolio_by_date = dict(extract_decimal_returns(series["portfolio_returns"]))
    benchmark_by_date = dict(extract_decimal_returns(series["benchmark_returns"]))
    aligned_dates = sorted(set(portfolio_by_date) & set(benchmark_by_date))
    assert aligned_dates, "expected live upstream benchmark returns aligned with portfolio returns"

    portfolio_returns = [portfolio_by_date[date_value] for date_value in aligned_dates]
    benchmark_returns = [benchmark_by_date[date_value] for date_value in aligned_dates]
    body = risk_response.json()
    period = body["results"]["YTD"]
    metrics = period["metrics"]

    assert period["portfolio_observation_count"] == len(portfolio_by_date)
    assert period["benchmark_observation_count"] == len(benchmark_by_date)
    assert period["aligned_benchmark_observation_count"] == len(aligned_dates)
    assert body["metadata"]["benchmark_context"] == {
        "requested": True,
        "requested_metrics": ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"],
    }
    assert period["benchmark_context"]["reason"] == "APPLIED"
    assert period["benchmark_context"]["requested_metric_count"] == 3
    assert metrics["VOLATILITY"]["value"] == pytest.approx(
        _annualized_volatility(portfolio_returns), abs=1e-12
    )
    assert metrics["BETA"]["value"] == pytest.approx(
        _beta(portfolio_returns, benchmark_returns), abs=1e-12
    )
    assert metrics["TRACKING_ERROR"]["value"] == pytest.approx(
        _tracking_error(portfolio_returns, benchmark_returns), abs=1e-12
    )
    assert metrics["INFORMATION_RATIO"]["value"] == pytest.approx(
        _information_ratio(portfolio_returns, benchmark_returns), abs=1e-12
    )
