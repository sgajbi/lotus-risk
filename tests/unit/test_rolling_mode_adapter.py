import asyncio
from typing import Any, cast

import pytest

from app.contracts.rolling import RollingStatefulInput
from app.services.rolling_mode_adapter import (
    _build_stateful_source_request,
    calculate_rolling_metrics_stateful,
)
from app.upstream_errors import UpstreamServiceError
from tests.support.lotus_core_fakes import RecordingLotusCoreReferenceClient
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.risk_free_series_payloads import build_risk_free_series_response


class _StubLotusCoreClientPortfolioCurrencyOnly(RecordingLotusCoreReferenceClient):
    def __init__(self, *, reporting_currency: str = "USD") -> None:
        super().__init__(
            snapshot_response={"valuation_context": {"portfolio_currency": reporting_currency}}
        )


class _StubLotusCoreClientMissingValuationContext(RecordingLotusCoreReferenceClient):
    def __init__(self) -> None:
        super().__init__(snapshot_response={"not_valuation_context": {}})


class _StubLotusCoreClientMissingCurrencies(RecordingLotusCoreReferenceClient):
    def __init__(self) -> None:
        super().__init__(
            snapshot_response={
                "valuation_context": {"portfolio_currency": "", "reporting_currency": ""}
            }
        )


def _stateful_input(metrics: list[str]) -> RollingStatefulInput:
    return RollingStatefulInput.model_validate(
        {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-01-05",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "rolling_options": {
                "window_lengths": [2],
                "metrics": metrics,
            },
        }
    )


def _portfolio_only_payload() -> dict[str, object]:
    return {
        "series": {
            "portfolio_returns": [
                {"date": "2026-01-02", "return_value": "0.0100"},
                {"date": "2026-01-03", "return_value": "-0.0200"},
            ]
        }
    }


def _risk_free_payload() -> dict[str, object]:
    return build_risk_free_series_response(
        points=[
            {
                "series_date": "2026-01-02",
                "value": "0.0365",
                "value_convention": "annualized_rate",
            },
            {
                "series_date": "2026-01-03",
                "value": "0.0365",
                "value_convention": "annualized_rate",
            },
            {
                "series_date": "2026-01-04",
                "value": "0.0365",
                "value_convention": "annualized_rate",
            },
        ]
    )


def test_build_stateful_source_request_selection_flags() -> None:
    payload = _build_stateful_source_request(
        _stateful_input(["ROLLING_VOLATILITY", "ROLLING_BETA", "ROLLING_SHARPE"])
    )
    assert payload["window"] == {
        "mode": "EXPLICIT",
        "from_date": "2026-01-01",
        "to_date": "2026-01-05",
    }
    selection = payload["series_selection"]
    assert selection["include_portfolio"] is True
    assert selection["include_benchmark"] is True
    assert selection["include_risk_free"] is False


def test_stateful_adapter_happy_path() -> None:
    client = RecordingLotusPerformanceClient(
        response_payload={
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "0.0100"},
                    {"date": "2026-01-03", "return_value": "-0.0200"},
                    {"date": "2026-01-04", "return_value": "0.0050"},
                ],
                "benchmark_returns": [
                    {"date": "2026-01-02", "return_value": "0.0080"},
                    {"date": "2026-01-03", "return_value": "-0.0150"},
                    {"date": "2026-01-04", "return_value": "0.0040"},
                ],
            }
        }
    )
    core_client = RecordingLotusCoreReferenceClient(risk_free_response=_risk_free_payload())

    response = asyncio.run(
        calculate_rolling_metrics_stateful(
            _stateful_input(["ROLLING_VOLATILITY", "ROLLING_BETA", "ROLLING_SHARPE"]),
            performance_client=client,
            core_client=core_client,
            correlation_id="corr-rolling-stateful",
        )
    )

    assert client.correlation_id == "corr-rolling-stateful"
    assert client.request_payload is not None
    assert client.request_payload["input_mode"] == "stateful"
    assert client.request_payload["stateful_input"] == {}
    assert client.request_payload["reporting_currency"] == "USD"
    assert core_client.snapshot_calls[0]["portfolio_id"] == "DEMO_DPM_EUR_001"
    assert core_client.risk_free_calls[0]["correlation_id"] == "corr-rolling-stateful"
    assert response.input_mode.value == "stateful"
    assert "YTD" in response.results


def test_stateful_adapter_requires_series_object() -> None:
    client = RecordingLotusPerformanceClient(response_payload={"not_series": {}})
    with pytest.raises(ValueError, match="missing 'series' object"):
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_VOLATILITY"]),
                performance_client=client,
                correlation_id=None,
            )
        )


def test_stateful_adapter_requires_benchmark_when_metric_requested() -> None:
    client = RecordingLotusPerformanceClient(response_payload=_portfolio_only_payload())
    with pytest.raises(ValueError, match="no benchmark returns"):
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_BETA"]),
                performance_client=client,
                core_client=None,
                correlation_id=None,
            )
        )


def test_stateful_adapter_requires_risk_free_for_sharpe() -> None:
    client = RecordingLotusPerformanceClient(response_payload=_portfolio_only_payload())
    with pytest.raises(UpstreamServiceError, match="no usable risk-free returns") as exc_info:
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_SHARPE"]),
                performance_client=client,
                core_client=RecordingLotusCoreReferenceClient(),
                correlation_id=None,
            )
        )
    assert exc_info.value.details["risk_free_currency"] == "USD"
    assert exc_info.value.details["risk_free_total_points"] == 0
    assert exc_info.value.details["risk_free_missing_dates_count"] == 4


def test_stateful_adapter_ignores_coverage_probe_failures_for_missing_risk_free() -> None:
    class _CoverageUnavailableCoreClient(RecordingLotusCoreReferenceClient):
        async def get_risk_free_coverage(
            self,
            *,
            currency: str,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            raise UpstreamServiceError(
                service="lotus-core",
                operation="/integration/reference/risk-free-series/coverage",
                status_code=503,
                code="UPSTREAM_UNAVAILABLE",
                message="lotus-core /integration/reference/risk-free-series/coverage unavailable: down",
                details={"service": "lotus-core"},
                retryable=True,
            )

    client = RecordingLotusPerformanceClient(response_payload=_portfolio_only_payload())
    with pytest.raises(UpstreamServiceError, match="no usable risk-free returns") as exc_info:
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_SHARPE"]),
                performance_client=client,
                core_client=_CoverageUnavailableCoreClient(),
                correlation_id=None,
            )
        )

    assert exc_info.value.details["risk_free_currency"] == "USD"
    assert "risk_free_total_points" not in exc_info.value.details


def test_stateful_adapter_rejects_invalid_return_value() -> None:
    client = RecordingLotusPerformanceClient(
        response_payload={
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "not-a-number"},
                    {"date": "2026-01-03", "return_value": "0.0100"},
                ]
            }
        }
    )
    with pytest.raises(ValueError, match="Invalid return value"):
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_VOLATILITY"]),
                performance_client=client,
                core_client=None,
                correlation_id=None,
            )
        )


def test_stateful_adapter_requires_core_snapshot_when_sharpe_needs_reporting_currency() -> None:
    client = RecordingLotusPerformanceClient(response_payload=_portfolio_only_payload())
    with pytest.raises(ValueError, match="reporting_currency is required for rolling Sharpe"):
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_SHARPE"]),
                performance_client=client,
                core_client=None,
                correlation_id=None,
            )
        )


def test_stateful_adapter_requires_core_client_for_explicit_risk_free_sourcing() -> None:
    client = RecordingLotusPerformanceClient(response_payload=_portfolio_only_payload())
    request = _stateful_input(["ROLLING_SHARPE"]).model_copy(update={"reporting_currency": "CHF"})
    with pytest.raises(ValueError, match="lotus-core client is required"):
        asyncio.run(
            calculate_rolling_metrics_stateful(
                request,
                performance_client=client,
                core_client=None,
                correlation_id="corr-explicit-ccy",
            )
        )


def test_stateful_adapter_skips_core_snapshot_when_reporting_currency_is_explicit() -> None:
    client = RecordingLotusPerformanceClient(response_payload=_portfolio_only_payload())
    core_client = RecordingLotusCoreReferenceClient(risk_free_response=_risk_free_payload())
    request = _stateful_input(["ROLLING_SHARPE"]).model_copy(update={"reporting_currency": "CHF"})
    response = asyncio.run(
        calculate_rolling_metrics_stateful(
            request,
            performance_client=client,
            core_client=core_client,
            correlation_id="corr-explicit-ccy",
        )
    )
    assert client.request_payload is not None
    assert client.request_payload["reporting_currency"] == "CHF"
    assert not core_client.snapshot_calls
    assert core_client.risk_free_calls
    assert response.scope.reporting_currency == "CHF"


def test_stateful_adapter_uses_portfolio_currency_when_reporting_currency_missing() -> None:
    client = RecordingLotusPerformanceClient(response_payload=_portfolio_only_payload())
    core_client = _StubLotusCoreClientPortfolioCurrencyOnly(reporting_currency="EUR")
    core_client.risk_free_response = _risk_free_payload()
    response = asyncio.run(
        calculate_rolling_metrics_stateful(
            _stateful_input(["ROLLING_SHARPE"]),
            performance_client=client,
            core_client=core_client,
            correlation_id="corr-portfolio-ccy",
        )
    )
    assert client.request_payload is not None
    assert client.request_payload["reporting_currency"] == "EUR"
    assert response.scope.reporting_currency == "EUR"


def test_stateful_adapter_rejects_missing_valuation_context() -> None:
    client = RecordingLotusPerformanceClient(response_payload=_portfolio_only_payload())
    with pytest.raises(ValueError, match="missing valuation_context"):
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_SHARPE"]),
                performance_client=client,
                core_client=_StubLotusCoreClientMissingValuationContext(),
                correlation_id=None,
            )
        )


def test_stateful_adapter_rejects_missing_portfolio_and_reporting_currency() -> None:
    client = RecordingLotusPerformanceClient(response_payload=_portfolio_only_payload())
    with pytest.raises(ValueError, match="missing portfolio/reporting currency"):
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_SHARPE"]),
                performance_client=client,
                core_client=_StubLotusCoreClientMissingCurrencies(),
                correlation_id=None,
            )
        )


def test_stateful_adapter_rejects_unknown_risk_free_value_convention() -> None:
    client = RecordingLotusPerformanceClient(response_payload=_portfolio_only_payload())
    core_client = RecordingLotusCoreReferenceClient(
        risk_free_response=build_risk_free_series_response(
            points=[
                {
                    "series_date": "2026-01-02",
                    "value": "0.0365",
                    "value_convention": "mystery",
                }
            ]
        )
    )
    with pytest.raises(ValueError, match="Unsupported risk-free value_convention"):
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_SHARPE"]),
                performance_client=client,
                core_client=core_client,
                correlation_id=None,
            )
        )


def test_stateful_adapter_sources_risk_free_after_returns_for_si_window() -> None:
    client = RecordingLotusPerformanceClient(
        response_payload={
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "0.0100"},
                    {"date": "2026-01-03", "return_value": "-0.0200"},
                    {"date": "2026-01-04", "return_value": "0.0050"},
                ],
            }
        }
    )
    core_client = RecordingLotusCoreReferenceClient(risk_free_response=_risk_free_payload())
    request = RollingStatefulInput.model_validate(
        {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-01-04",
            "reporting_currency": "USD",
            "periods": [{"type": "SI", "name": "SI"}],
            "rolling_options": {
                "window_lengths": [2],
                "metrics": ["ROLLING_SHARPE"],
            },
        }
    )

    response = asyncio.run(
        calculate_rolling_metrics_stateful(
            request,
            performance_client=client,
            core_client=core_client,
            correlation_id="corr-si-risk-free",
        )
    )

    assert client.request_payload is not None
    assert client.request_payload["window"] == {"mode": "RELATIVE", "period": "SI"}
    risk_free_payload = cast(dict[str, Any], core_client.risk_free_calls[0]["request_payload"])
    assert risk_free_payload["window"] == {
        "start_date": "2026-01-02",
        "end_date": "2026-01-04",
    }
    assert response.results["SI"].error is None
