from __future__ import annotations

import os
from datetime import date

import httpx
import numpy as np
import pytest

from app.contracts.risk import RiskRequestPeriod
from app.services.stateful_returns_request import build_stateful_returns_series_request
from tests.support.live_portfolio_matrix import (
    HISTORICAL_ATTRIBUTION_ACTIVE_RISK_GROUPINGS,
    live_as_of_date,
    live_portfolio_id,
)
from tests.support.live_returns_series import (
    extract_decimal_returns,
    fetch_live_benchmark_exposure_context,
    fetch_live_returns_series,
)


def _live_enabled() -> bool:
    return os.getenv("LOTUS_RISK_RUN_LIVE_ATTRIBUTION") == "1"


pytestmark = pytest.mark.skipif(
    not _live_enabled(),
    reason="set LOTUS_RISK_RUN_LIVE_ATTRIBUTION=1 to run live attribution characterization",
)


RISK_BASE_URL = os.getenv("LOTUS_RISK_BASE_URL", "http://localhost:8130")
PERFORMANCE_BASE_URL = os.getenv("LOTUS_PERFORMANCE_BASE_URL", "http://localhost:8002")
PORTFOLIO_ID = live_portfolio_id()
AS_OF_DATE = date.fromisoformat(live_as_of_date())
ANNUALIZATION_BASIS = 252


def _business_day_returns(rows: list[tuple[str, float]]) -> list[tuple[str, float]]:
    return [
        (date_value, return_value)
        for date_value, return_value in rows
        if date.fromisoformat(date_value).weekday() < 5
    ]


def _returns_request(*, include_benchmark: bool) -> dict[str, object]:
    return build_stateful_returns_series_request(
        portfolio_id=PORTFOLIO_ID,
        as_of_date=AS_OF_DATE,
        periods=[RiskRequestPeriod(type="YTD", name="YTD")],
        frequency="DAILY",
        metric_basis="NET",
        reporting_currency=None,
        include_benchmark=include_benchmark,
        include_risk_free=False,
        missing_data_policy="ALLOW_PARTIAL",
    )


def _live_portfolio_and_benchmark_returns() -> tuple[list[float], list[float]]:
    returns_body = fetch_live_returns_series(
        base_url=PERFORMANCE_BASE_URL,
        request_payload=_returns_request(include_benchmark=True),
    )
    series = returns_body["series"]
    portfolio_by_date = dict(
        _business_day_returns(extract_decimal_returns(series["portfolio_returns"]))
    )
    benchmark_by_date = dict(
        _business_day_returns(extract_decimal_returns(series["benchmark_returns"]))
    )
    aligned_dates = sorted(set(portfolio_by_date) & set(benchmark_by_date))
    assert aligned_dates, "expected live benchmark returns aligned with portfolio returns"
    return (
        [portfolio_by_date[date_value] for date_value in aligned_dates],
        [benchmark_by_date[date_value] for date_value in aligned_dates],
    )


def _annualized_volatility(returns: list[float]) -> float:
    return float(np.std(returns, ddof=1) * np.sqrt(ANNUALIZATION_BASIS))


def _annualized_tracking_error(
    portfolio_returns: list[float], benchmark_returns: list[float]
) -> float:
    active_returns = np.array(portfolio_returns) - np.array(benchmark_returns)
    return float(np.std(active_returns, ddof=1) * np.sqrt(ANNUALIZATION_BASIS))


def _benchmark_exposure_request(*, grouping_dimensions: list[str]) -> dict[str, object]:
    start_of_year = date(AS_OF_DATE.year, 1, 1)
    return {
        "portfolio_id": PORTFOLIO_ID,
        "as_of_date": AS_OF_DATE.isoformat(),
        "window": {
            "start_date": start_of_year.isoformat(),
            "end_date": AS_OF_DATE.isoformat(),
        },
        "frequency": "DAILY",
        "grouping_dimensions": grouping_dimensions,
        "page": {"page_size": 1000, "page_token": None},
    }


def _stateful_active_risk_payload(*, grouping_dimensions: list[str]) -> dict[str, object]:
    return {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": PORTFOLIO_ID,
            "as_of_date": AS_OF_DATE.isoformat(),
            "periods": [{"type": "YTD", "name": "YTD"}],
            "attribution_options": {
                "attribution_types": ["ACTIVE_RISK"],
                "metrics": ["TRACKING_ERROR"],
                "grouping_dimensions": grouping_dimensions,
            },
        },
    }


def _stateful_total_risk_payload(*, grouping_dimensions: list[str]) -> dict[str, object]:
    return {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": PORTFOLIO_ID,
            "as_of_date": AS_OF_DATE.isoformat(),
            "periods": [{"type": "YTD", "name": "YTD"}],
            "attribution_options": {
                "attribution_types": ["TOTAL_RISK"],
                "metrics": ["VOLATILITY"],
                "grouping_dimensions": grouping_dimensions,
            },
        },
    }


@pytest.mark.parametrize("grouping_dimension", ["SECTOR", "ISSUER"])
def test_live_benchmark_exposure_context_supports_grouping_dimension(
    grouping_dimension: str,
) -> None:
    supported = fetch_live_benchmark_exposure_context(
        base_url=PERFORMANCE_BASE_URL,
        request_payload=_benchmark_exposure_request(grouping_dimensions=[grouping_dimension]),
    )

    assert supported["source_service"] == "lotus-performance"
    assert supported["contract_version"] == "v1"
    assert supported["metadata"]["source_system"] == "lotus-core"
    assert supported["metadata"]["served_by"] == "lotus-performance"
    assert supported["rows"], f"expected live {grouping_dimension} benchmark exposure rows"
    assert {row["grouping_dimension"] for row in supported["rows"]} == {grouping_dimension}


def test_live_stateful_historical_attribution_supports_sector_active_risk() -> None:
    supported = fetch_live_benchmark_exposure_context(
        base_url=PERFORMANCE_BASE_URL,
        request_payload=_benchmark_exposure_request(grouping_dimensions=["SECTOR"]),
    )
    benchmark_group_keys = {str(row["group_key"]) for row in supported["rows"]}
    assert benchmark_group_keys, "expected benchmark exposure context group keys"

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{RISK_BASE_URL}/analytics/risk/historical-attribution",
            json=_stateful_active_risk_payload(grouping_dimensions=["SECTOR"]),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateful"
    assert body["metadata"]["requested_attribution_types"] == ["ACTIVE_RISK"]
    assert body["metadata"]["requested_metrics"] == ["TRACKING_ERROR"]
    assert body["metadata"]["requested_grouping_dimensions"] == ["SECTOR"]
    assert body["metadata"]["stateful_active_risk_supported_grouping_dimensions"] == list(
        HISTORICAL_ATTRIBUTION_ACTIVE_RISK_GROUPINGS
    )
    assert body["metadata"]["stateful_active_risk_gated_grouping_dimensions"] == []

    period = body["results"]["YTD"]
    assert period["error"] is None
    attribution_sets = period["attribution_sets"]
    assert attribution_sets, "expected live attribution set"
    attribution_set = attribution_sets[0]
    portfolio_returns, benchmark_returns = _live_portfolio_and_benchmark_returns()
    assert attribution_set["attribution_type"] == "ACTIVE_RISK"
    assert attribution_set["metric"] == "TRACKING_ERROR"
    assert attribution_set["grouping_dimension"] == "SECTOR"
    assert attribution_set["total_value"] == pytest.approx(
        _annualized_tracking_error(portfolio_returns, benchmark_returns),
        abs=1e-12,
    )
    assert attribution_set["contributors"], "expected live contributors for supported SECTOR path"
    contributor_keys = {contributor["group_key"] for contributor in attribution_set["contributors"]}
    assert all(key.startswith("SECTOR_") for key in contributor_keys)
    assert contributor_keys & benchmark_group_keys
    if attribution_set["total_value"] is not None and attribution_set["reconciled_sum"] is not None:
        assert attribution_set["residual"] == pytest.approx(
            attribution_set["total_value"] - attribution_set["reconciled_sum"],
            abs=1e-12,
        )


def test_live_stateful_historical_attribution_supports_sector_total_risk() -> None:
    portfolio_returns, _ = _live_portfolio_and_benchmark_returns()

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{RISK_BASE_URL}/analytics/risk/historical-attribution",
            json=_stateful_total_risk_payload(grouping_dimensions=["SECTOR"]),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateful"
    assert body["metadata"]["requested_attribution_types"] == ["TOTAL_RISK"]
    assert body["metadata"]["requested_metrics"] == ["VOLATILITY"]
    assert body["metadata"]["requested_grouping_dimensions"] == ["SECTOR"]

    attribution_set = body["results"]["YTD"]["attribution_sets"][0]
    assert attribution_set["attribution_type"] == "TOTAL_RISK"
    assert attribution_set["metric"] == "VOLATILITY"
    assert attribution_set["grouping_dimension"] == "SECTOR"
    assert attribution_set["quality_flags"] == []
    assert attribution_set["contributors"], "expected live total-risk contributors"
    assert attribution_set["total_value"] == pytest.approx(
        _annualized_volatility(portfolio_returns),
        abs=1e-12,
    )
    assert attribution_set["reconciled_sum"] == pytest.approx(
        sum(
            contributor["component_contribution"] for contributor in attribution_set["contributors"]
        ),
        abs=1e-12,
    )
    assert attribution_set["residual"] == pytest.approx(
        attribution_set["total_value"] - attribution_set["reconciled_sum"],
        abs=1e-12,
    )


@pytest.mark.parametrize("grouping_dimension", ["POSITION", "ASSET_CLASS", "ISSUER"])
def test_live_stateful_historical_attribution_supports_other_active_risk_groupings(
    grouping_dimension: str,
) -> None:
    supported = fetch_live_benchmark_exposure_context(
        base_url=PERFORMANCE_BASE_URL,
        request_payload=_benchmark_exposure_request(grouping_dimensions=[grouping_dimension]),
    )
    assert supported["rows"], f"expected live {grouping_dimension} benchmark exposure rows"
    assert {row["grouping_dimension"] for row in supported["rows"]} == {grouping_dimension}
    portfolio_returns, benchmark_returns = _live_portfolio_and_benchmark_returns()

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{RISK_BASE_URL}/analytics/risk/historical-attribution",
            json=_stateful_active_risk_payload(grouping_dimensions=[grouping_dimension]),
        )

    assert response.status_code == 200
    attribution_set = response.json()["results"]["YTD"]["attribution_sets"][0]
    assert attribution_set["attribution_type"] == "ACTIVE_RISK"
    assert attribution_set["metric"] == "TRACKING_ERROR"
    assert attribution_set["grouping_dimension"] == grouping_dimension
    assert attribution_set["quality_flags"] == []
    assert attribution_set["contributors"], f"expected {grouping_dimension} contributors"
    assert attribution_set["total_value"] == pytest.approx(
        _annualized_tracking_error(portfolio_returns, benchmark_returns),
        abs=1e-12,
    )
    assert attribution_set["reconciled_sum"] == pytest.approx(
        sum(
            contributor["component_contribution"] for contributor in attribution_set["contributors"]
        ),
        abs=1e-12,
    )
    assert attribution_set["residual"] == pytest.approx(
        attribution_set["total_value"] - attribution_set["reconciled_sum"],
        abs=1e-12,
    )
