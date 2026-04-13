from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date
from statistics import NormalDist
from typing import cast

import httpx
import numpy as np
import pandas as pd
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
SORTINO_MAR_ANNUAL_RATE = 0.05
VAR_CONFIDENCE = 0.95


def _annualized_volatility(returns: list[float]) -> float:
    return float(np.std(returns, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR) * 100.0)


def _business_day_returns(rows: list[tuple[str, float]]) -> list[tuple[str, float]]:
    return [
        (date_value, return_value)
        for date_value, return_value in rows
        if date.fromisoformat(date_value).weekday() < 5
    ]


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


def _annual_to_periodic(rate: float) -> float:
    return float((1.0 + rate) ** (1.0 / ANNUALIZATION_FACTOR) - 1.0)


def _sortino(
    portfolio_returns: list[float], *, mar_annual_rate: float
) -> tuple[float, int, float, float]:
    periodic_mar = _annual_to_periodic(mar_annual_rate)
    returns = np.array(portfolio_returns)
    downside = returns - periodic_mar
    downside = downside[downside < 0]
    assert len(downside) > 0, "live Sortino characterization requires downside observations"
    downside_deviation = float(np.sqrt(np.mean(downside**2)))
    excess_return = float(np.mean(returns) - periodic_mar)
    sortino = float((excess_return / downside_deviation) * np.sqrt(ANNUALIZATION_FACTOR))
    return sortino, int(len(downside)), downside_deviation, excess_return


def _historical_var(
    portfolio_returns: list[float], *, confidence: float
) -> tuple[float, float, int]:
    percentage_point_returns = np.array(portfolio_returns) * 100.0
    base_var = float(np.percentile(percentage_point_returns, (1.0 - confidence) * 100.0))
    tail = percentage_point_returns[percentage_point_returns <= base_var]
    expected_shortfall = float(np.mean(tail)) if len(tail) > 0 else base_var
    return base_var, expected_shortfall, int(len(tail))


def _gaussian_var(
    portfolio_returns: list[float], *, confidence: float, horizon_days: int
) -> tuple[float, float, float, int]:
    percentage_point_returns = pd.Series(np.array(portfolio_returns) * 100.0, dtype="float64")
    z_score = NormalDist().inv_cdf(1.0 - confidence)
    base_var = float(
        percentage_point_returns.mean() + percentage_point_returns.std(ddof=1) * z_score
    )
    tail = percentage_point_returns[percentage_point_returns <= base_var]
    base_expected_shortfall = float(tail.mean()) if not tail.empty else base_var
    scale = float(np.sqrt(horizon_days))
    return base_var * scale, base_var, base_expected_shortfall * scale, int(tail.count())


def _cornish_fisher_var(
    portfolio_returns: list[float], *, confidence: float, horizon_days: int
) -> tuple[float, float, float, int]:
    percentage_point_returns = pd.Series(np.array(portfolio_returns) * 100.0, dtype="float64")
    z_score = NormalDist().inv_cdf(1.0 - confidence)
    skew = float(cast(float, percentage_point_returns.skew()))
    kurtosis = float(cast(float, percentage_point_returns.kurt()))
    z_cf = z_score
    z_cf += ((z_score**2) - 1.0) * skew / 6.0
    z_cf += ((z_score**3) - 3.0 * z_score) * kurtosis / 24.0
    z_cf -= ((2.0 * z_score**3) - 5.0 * z_score) * (skew**2) / 36.0
    base_var = float(percentage_point_returns.mean() + percentage_point_returns.std(ddof=1) * z_cf)
    tail = percentage_point_returns[percentage_point_returns <= base_var]
    base_expected_shortfall = float(tail.mean()) if not tail.empty else base_var
    scale = float(np.sqrt(horizon_days))
    return base_var * scale, base_var, base_expected_shortfall * scale, int(tail.count())


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
            "metrics": [
                "VOLATILITY",
                "BETA",
                "TRACKING_ERROR",
                "INFORMATION_RATIO",
                "SORTINO",
                "VAR",
            ],
            "options": {
                "frequency": "DAILY",
                "mar_annual_rate": SORTINO_MAR_ANNUAL_RATE,
                "var": {
                    "method": "HISTORICAL",
                    "confidence": VAR_CONFIDENCE,
                    "horizon_days": 1,
                    "include_expected_shortfall": True,
                },
            },
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
    upstream_portfolio_returns = extract_decimal_returns(series["portfolio_returns"])
    upstream_benchmark_returns = extract_decimal_returns(series["benchmark_returns"])
    portfolio_by_date = dict(_business_day_returns(upstream_portfolio_returns))
    benchmark_by_date = dict(_business_day_returns(upstream_benchmark_returns))
    aligned_dates = sorted(set(portfolio_by_date) & set(benchmark_by_date))
    assert aligned_dates, "expected live upstream benchmark returns aligned with portfolio returns"
    assert all(date.fromisoformat(date_value).weekday() < 5 for date_value in portfolio_by_date)
    assert len(portfolio_by_date) <= len(upstream_portfolio_returns)

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

    sortino, downside_count, downside_deviation, excess_return = _sortino(
        portfolio_returns,
        mar_annual_rate=SORTINO_MAR_ANNUAL_RATE,
    )
    sortino_metric = metrics["SORTINO"]
    assert sortino_metric["value"] == pytest.approx(sortino, abs=1e-12)
    assert sortino_metric["details"]["periodic_mar"] == pytest.approx(
        _annual_to_periodic(SORTINO_MAR_ANNUAL_RATE), abs=1e-15
    )
    assert sortino_metric["details"]["downside_observation_count"] == downside_count
    assert sortino_metric["details"]["downside_deviation"] == pytest.approx(
        downside_deviation, abs=1e-15
    )
    assert sortino_metric["details"]["excess_return"] == pytest.approx(excess_return, abs=1e-15)

    historical_var, expected_shortfall, tail_count = _historical_var(
        portfolio_returns, confidence=VAR_CONFIDENCE
    )
    var_metric = metrics["VAR"]
    assert var_metric["value"] == pytest.approx(historical_var, abs=1e-12)
    assert var_metric["details"]["method"] == "HISTORICAL"
    assert var_metric["details"]["confidence"] == VAR_CONFIDENCE
    assert var_metric["details"]["base_var"] == pytest.approx(historical_var, abs=1e-12)
    assert var_metric["details"]["expected_shortfall"] == pytest.approx(
        expected_shortfall, abs=1e-12
    )
    assert var_metric["details"]["tail_observation_count"] == tail_count


@pytest.mark.parametrize(
    ("method", "horizon_days", "reference"),
    [
        ("GAUSSIAN", 5, _gaussian_var),
        ("CORNISH_FISHER", 10, _cornish_fisher_var),
    ],
)
def test_live_stateful_risk_calculate_reconciles_parametric_var_methods(
    method: str,
    horizon_days: int,
    reference: Callable[..., tuple[float, float, float, int]],
) -> None:
    returns_payload = build_stateful_returns_series_request(
        portfolio_id=PORTFOLIO_ID,
        as_of_date=date.fromisoformat(AS_OF_DATE),
        periods=[RiskRequestPeriod(type="YTD", name="YTD")],
        frequency="DAILY",
        metric_basis="NET",
        reporting_currency=None,
        include_benchmark=False,
        include_risk_free=False,
        missing_data_policy="FAIL_FAST",
    )
    risk_payload = {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": PORTFOLIO_ID,
            "as_of_date": AS_OF_DATE,
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VAR"],
            "options": {
                "frequency": "DAILY",
                "var": {
                    "method": method,
                    "confidence": VAR_CONFIDENCE,
                    "horizon_days": horizon_days,
                    "include_expected_shortfall": True,
                },
            },
        },
    }

    upstream_body = fetch_live_returns_series(
        base_url=PERFORMANCE_BASE_URL,
        request_payload=returns_payload,
    )
    with httpx.Client(timeout=30.0) as client:
        risk_response = client.post(f"{RISK_BASE_URL}/analytics/risk/calculate", json=risk_payload)
        risk_response.raise_for_status()

    portfolio_returns = [
        value
        for _, value in _business_day_returns(
            extract_decimal_returns(upstream_body["series"]["portfolio_returns"])
        )
    ]
    value, base_var, expected_shortfall, tail_count = reference(
        portfolio_returns,
        confidence=VAR_CONFIDENCE,
        horizon_days=horizon_days,
    )
    metric = risk_response.json()["results"]["YTD"]["metrics"]["VAR"]

    assert metric["value"] == pytest.approx(value, abs=1e-12)
    assert metric["details"]["method"] == method
    assert metric["details"]["confidence"] == VAR_CONFIDENCE
    assert metric["details"]["horizon_days"] == horizon_days
    assert metric["details"]["horizon_scale_factor"] == pytest.approx(
        np.sqrt(horizon_days), abs=1e-15
    )
    assert metric["details"]["base_var"] == pytest.approx(base_var, abs=1e-12)
    assert metric["details"]["expected_shortfall"] == pytest.approx(expected_shortfall, abs=1e-12)
    assert metric["details"]["tail_observation_count"] == tail_count
