from __future__ import annotations

import asyncio

import pytest

from app.contracts.risk import StatefulRiskInput
from app.services.risk_mode_adapter import (
    _build_stateful_source_request,
    _portfolio_open_date,
    calculate_risk_stateful,
)
from app.upstream_errors import UpstreamServiceError
from tests.support.lotus_core_fakes import RecordingLotusCoreReferenceClient
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import build_returns_series_response


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


def _risk_free_payload() -> dict[str, object]:
    return {
        "points": [
            {
                "series_date": "2025-01-02",
                "value": "0.025",
                "value_convention": "annualized_rate",
            },
            {
                "series_date": "2025-01-03",
                "value": "0.025",
                "value_convention": "annualized_rate",
            },
            {
                "series_date": "2025-01-06",
                "value": "0.025",
                "value_convention": "annualized_rate",
            },
        ]
    }


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
    assert payload["series_selection"]["include_risk_free"] is False


def test_stateful_source_payload_does_not_broker_risk_free_for_sharpe() -> None:
    stateful = _stateful_input().model_copy(update={"metrics": ["SHARPE"]})

    payload = _build_stateful_source_request(stateful)

    assert payload["series_selection"]["include_risk_free"] is False


def test_stateful_source_payload_passes_benchmark_override_for_relative_metrics() -> None:
    stateful = _stateful_input().model_copy(
        update={
            "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
            "metrics": ["TRACKING_ERROR"],
        }
    )

    payload = _build_stateful_source_request(stateful)

    assert payload["series_selection"]["include_benchmark"] is True
    assert payload["benchmark"] == {
        "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
        "return_source": "calculated",
    }


def test_calculate_risk_stateful_characterization() -> None:
    performance_client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=[
                ("2025-01-02", "0.0100"),
                ("2025-01-03", "-0.0050"),
                ("2025-01-06", "0.0030"),
            ]
        )
    )
    response = asyncio.run(
        calculate_risk_stateful(
            _stateful_input(),
            performance_client=performance_client,
            correlation_id="corr-risk-stateful",
        )
    )

    assert performance_client.request_payload is not None
    assert performance_client.correlation_id == "corr-risk-stateful"
    metrics = response.results["YTD"].metrics
    assert metrics["VOLATILITY"].value is not None
    assert metrics["VAR"].value is not None
    assert response.metadata.source_services == ["lotus-risk", "lotus-performance"]
    assert response.metadata.request_fingerprint is not None
    assert response.metadata.request_fingerprint.startswith("sha256:")
    assert list(response.metadata.upstream_request_fingerprints) == [
        "lotus-performance:/integration/returns/series"
    ]


def test_calculate_risk_stateful_applies_sourced_risk_free_for_sharpe() -> None:
    stateful = _stateful_input().model_copy(update={"metrics": ["SHARPE"]})
    performance_client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=[
                ("2025-01-02", "0.0100"),
                ("2025-01-03", "-0.0050"),
                ("2025-01-06", "0.0030"),
            ],
        )
    )
    core_client = RecordingLotusCoreReferenceClient(risk_free_response=_risk_free_payload())

    response = asyncio.run(
        calculate_risk_stateful(
            stateful,
            performance_client=performance_client,
            core_client=core_client,
            correlation_id="corr-risk-stateful-rf",
        )
    )

    assert performance_client.request_payload is not None
    assert performance_client.request_payload["series_selection"]["include_risk_free"] is False
    assert core_client.risk_free_calls
    risk_free_request = core_client.risk_free_calls[0]["request_payload"]
    assert risk_free_request == {
        "currency": "USD",
        "as_of_date": "2025-01-07",
        "series_mode": "annualized_rate_series",
        "window": {"start_date": "2025-01-01", "end_date": "2025-01-07"},
        "frequency": "daily",
    }
    assert response.metadata.risk_free_context.reason == "ANNUAL_RATE_APPLIED"
    assert response.metadata.risk_free_context.periodic_rate > 0
    assert response.metadata.risk_free_annual_rate is not None
    assert response.metadata.source_services == [
        "lotus-risk",
        "lotus-performance",
        "lotus-core",
    ]
    assert set(response.metadata.upstream_request_fingerprints) == {
        "lotus-performance:/integration/returns/series",
        "lotus-core:/integration/reference/risk-free-series",
    }
    sharpe = response.results["YTD"].metrics["SHARPE"]
    assert sharpe.details is not None
    periodic_risk_free_rate = sharpe.details["periodic_risk_free_rate"]
    assert isinstance(periodic_risk_free_rate, float)
    assert periodic_risk_free_rate > 0


def test_calculate_risk_stateful_rejects_missing_risk_free_for_sharpe() -> None:
    stateful = _stateful_input().model_copy(update={"metrics": ["SHARPE"]})
    performance_client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=[
                ("2025-01-02", "0.0100"),
                ("2025-01-03", "-0.0050"),
                ("2025-01-06", "0.0030"),
            ],
        )
    )
    core_client = RecordingLotusCoreReferenceClient(risk_free_response={"points": []})

    with pytest.raises(UpstreamServiceError, match="no usable risk-free returns"):
        asyncio.run(
            calculate_risk_stateful(
                stateful,
                performance_client=performance_client,
                core_client=core_client,
                correlation_id="corr-risk-stateful-rf",
            )
        )


def test_calculate_risk_stateful_requires_core_client_for_sharpe() -> None:
    stateful = _stateful_input().model_copy(update={"metrics": ["SHARPE"]})
    performance_client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=[
                ("2025-01-02", "0.0100"),
                ("2025-01-03", "-0.0050"),
                ("2025-01-06", "0.0030"),
            ]
        )
    )

    with pytest.raises(ValueError, match="lotus-core client is required"):
        asyncio.run(
            calculate_risk_stateful(
                stateful,
                performance_client=performance_client,
                correlation_id="corr-risk-stateful-rf",
            )
        )


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
