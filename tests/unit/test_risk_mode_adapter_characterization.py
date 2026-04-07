from __future__ import annotations

import asyncio

import pytest

from app.contracts.risk import StatefulRiskInput
from app.services.risk_mode_adapter import _build_stateful_source_request, _portfolio_open_date, calculate_risk_stateful


class _StubPerformanceClient:
    def __init__(self) -> None:
        self.payload: dict[str, object] | None = None
        self.correlation_id: str | None = None

    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        self.payload = request_payload
        self.correlation_id = correlation_id
        return {
            "series": {
                "portfolio_returns": [
                    {"date": "2025-01-02", "return_value": "0.0100"},
                    {"date": "2025-01-03", "return_value": "-0.0050"},
                    {"date": "2025-01-06", "return_value": "0.0030"},
                ],
            }
        }


def _stateful_input() -> StatefulRiskInput:
    return StatefulRiskInput.model_validate(
        {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2025-01-07",
            "reporting_currency": "USD",
            "net_or_gross": "NET",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY", "VAR"],
            "options": {"frequency": "DAILY"},
        }
    )


def test_portfolio_open_date_falls_back_to_as_of_date_when_empty() -> None:
    assert (
        _portfolio_open_date([], as_of_date=_stateful_input().as_of_date)
        == _stateful_input().as_of_date
    )


def test_stateful_source_payload_characterization() -> None:
    payload = _build_stateful_source_request(_stateful_input())
    assert payload["input_mode"] == "stateful"
    assert payload["stateful_input"] == {}
    assert payload["window"] == {
        "mode": "EXPLICIT",
        "from_date": "2025-01-01",
        "to_date": "2025-01-07",
    }
    assert payload["frequency"] == "DAILY"
    assert payload["metric_basis"] == "NET"


def test_calculate_risk_stateful_characterization() -> None:
    performance_client = _StubPerformanceClient()
    response = asyncio.run(
        calculate_risk_stateful(
            _stateful_input(),
            performance_client=performance_client,
            correlation_id="corr-risk-stateful",
        )
    )

    assert performance_client.payload is not None
    assert performance_client.correlation_id == "corr-risk-stateful"
    metrics = response.results["YTD"].metrics
    assert metrics["VOLATILITY"].value is not None
    assert metrics["VAR"].value is not None


def test_calculate_risk_stateful_requires_series_payload() -> None:
    class _MissingSeriesClient:
        async def get_returns_series(
            self,
            *,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            return {}

    with pytest.raises(ValueError, match="missing 'series' object"):
        asyncio.run(
            calculate_risk_stateful(
                _stateful_input(),
                performance_client=_MissingSeriesClient(),
                correlation_id="corr-risk-stateful",
            )
        )


def test_calculate_risk_stateful_requires_portfolio_returns() -> None:
    class _EmptySeriesClient:
        async def get_returns_series(
            self,
            *,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            return {"series": {"portfolio_returns": []}}

    with pytest.raises(ValueError, match="no portfolio returns"):
        asyncio.run(
            calculate_risk_stateful(
                _stateful_input(),
                performance_client=_EmptySeriesClient(),
                correlation_id="corr-risk-stateful",
            )
        )

