from __future__ import annotations

import os
from datetime import date

import httpx
import pandas as pd
import pytest

from app.contracts.risk import RiskRequestPeriod
from app.services.stateful_returns_request import build_stateful_returns_series_request
from tests.support.live_returns_series import extract_decimal_returns, fetch_live_returns_series


def _live_enabled() -> bool:
    return os.getenv("LOTUS_RISK_RUN_LIVE_ROLLING") == "1"


pytestmark = pytest.mark.skipif(
    not _live_enabled(),
    reason="set LOTUS_RISK_RUN_LIVE_ROLLING=1 to run live rolling reconciliation",
)


RISK_BASE_URL = os.getenv("LOTUS_RISK_BASE_URL", "http://localhost:8130")
PERFORMANCE_BASE_URL = os.getenv("LOTUS_PERFORMANCE_BASE_URL", "http://localhost:8002")
PORTFOLIO_ID = os.getenv("LOTUS_RISK_LIVE_PORTFOLIO_ID", "PB_SG_GLOBAL_BAL_001")
AS_OF_DATE = os.getenv("LOTUS_RISK_LIVE_AS_OF_DATE", "2026-03-31")
ANNUALIZATION_BASIS = 252
WINDOW_LENGTH = 21


def _series(rows: list[tuple[str, float]]) -> pd.Series:
    return pd.Series(
        [value for _, value in rows],
        index=pd.to_datetime([date_value for date_value, _ in rows]),
        dtype="float64",
    ).sort_index()


def _summary(series: pd.Series) -> dict[str, float]:
    clean = series.dropna()
    assert not clean.empty, "expected rolling series to contain values"
    total_point_count = int(series.shape[0])
    computed_point_count = int(clean.count())
    warmup_point_count = min(total_point_count, WINDOW_LENGTH - 1)
    non_computed_point_count = total_point_count - computed_point_count
    return {
        "total_point_count": total_point_count,
        "computed_point_count": computed_point_count,
        "coverage_ratio": float(computed_point_count / total_point_count),
        "min_observations_required": WINDOW_LENGTH,
        "warmup_point_count": warmup_point_count,
        "non_computed_point_count": non_computed_point_count,
        "post_warmup_gap_point_count": max(non_computed_point_count - warmup_point_count, 0),
        "latest": float(clean.iloc[-1]),
        "average": float(clean.mean()),
        "minimum": float(clean.min()),
        "maximum": float(clean.max()),
        "p05": float(clean.quantile(0.05)),
        "p50": float(clean.quantile(0.50)),
        "p95": float(clean.quantile(0.95)),
    }


def test_live_stateful_rolling_reconciles_selected_metrics() -> None:
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
    rolling_payload = {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": PORTFOLIO_ID,
            "as_of_date": AS_OF_DATE,
            "periods": [{"type": "YTD", "name": "YTD"}],
            "rolling_options": {
                "window_lengths": [WINDOW_LENGTH],
                "metrics": [
                    "ROLLING_VOLATILITY",
                    "ROLLING_BETA",
                    "ROLLING_TRACKING_ERROR",
                ],
                "annualization_basis": ANNUALIZATION_BASIS,
                "include_time_series": False,
            },
        },
    }

    upstream_body = fetch_live_returns_series(
        base_url=PERFORMANCE_BASE_URL,
        request_payload=returns_payload,
    )
    with httpx.Client(timeout=30.0) as client:
        rolling_response = client.post(
            f"{RISK_BASE_URL}/analytics/risk/rolling-metrics",
            json=rolling_payload,
        )
        rolling_response.raise_for_status()

    series = upstream_body["series"]
    portfolio = _series(extract_decimal_returns(series["portfolio_returns"]))
    benchmark = _series(extract_decimal_returns(series["benchmark_returns"]))
    aligned = pd.merge(
        portfolio.to_frame("portfolio"),
        benchmark.to_frame("benchmark"),
        left_index=True,
        right_index=True,
        how="inner",
    )
    assert not aligned.empty, "expected aligned live benchmark returns"

    rolling_volatility = aligned["portfolio"].rolling(
        window=WINDOW_LENGTH, min_periods=WINDOW_LENGTH
    ).std(ddof=1) * (ANNUALIZATION_BASIS**0.5)
    active = aligned["portfolio"] - aligned["benchmark"]
    rolling_tracking_error = active.rolling(
        window=WINDOW_LENGTH, min_periods=WINDOW_LENGTH
    ).std(ddof=1) * (ANNUALIZATION_BASIS**0.5)
    rolling_beta = (
        aligned["portfolio"].rolling(window=WINDOW_LENGTH, min_periods=WINDOW_LENGTH).cov(
            aligned["benchmark"]
        )
        / aligned["benchmark"].rolling(window=WINDOW_LENGTH, min_periods=WINDOW_LENGTH).var(ddof=1)
    )

    body = rolling_response.json()
    period = body["results"]["YTD"]
    window = period["window_results"][0]
    summaries = window["metric_summaries"]

    assert body["metadata"]["benchmark_context"] == {
        "requested": True,
        "requested_metrics": [
            "ROLLING_BETA",
            "ROLLING_TRACKING_ERROR",
        ],
    }
    assert body["metadata"]["risk_free_context"] == {
        "requested": False,
        "requested_metrics": [],
    }
    assert period["series_count"] == len(portfolio)
    assert period["benchmark_series_count"] == len(benchmark)
    assert period["aligned_benchmark_series_count"] == len(aligned)
    assert period["risk_free_series_count"] == 0
    assert period["aligned_risk_free_series_count"] == 0
    assert period["benchmark_context"] == {
        "requested": True,
        "available": True,
        "aligned": True,
        "reason": "APPLIED",
    }
    assert period["risk_free_context"] == {
        "requested": False,
        "available": False,
        "aligned": False,
        "reason": "NOT_REQUESTED",
    }
    assert body["metadata"]["annualization_basis"] == ANNUALIZATION_BASIS
    assert body["metadata"]["alignment_policy"] == "INNER_JOIN"
    assert period["quality_flags"] == []
    assert period["error"] is None

    for metric_name, expected in {
        "ROLLING_VOLATILITY": _summary(rolling_volatility),
        "ROLLING_BETA": _summary(rolling_beta),
        "ROLLING_TRACKING_ERROR": _summary(rolling_tracking_error),
    }.items():
        actual = summaries[metric_name]
        assert actual["total_point_count"] == expected["total_point_count"]
        assert actual["computed_point_count"] == expected["computed_point_count"]
        assert actual["coverage_ratio"] == pytest.approx(expected["coverage_ratio"], abs=1e-12)
        assert actual["min_observations_required"] == expected["min_observations_required"]
        assert actual["warmup_point_count"] == expected["warmup_point_count"]
        assert actual["non_computed_point_count"] == expected["non_computed_point_count"]
        assert actual["post_warmup_gap_point_count"] == expected["post_warmup_gap_point_count"]
        assert actual["latest_observation_date"] == str(aligned.index[-1].date())
        for field, expected_value in expected.items():
            assert actual[field] == pytest.approx(expected_value, abs=1e-12)
