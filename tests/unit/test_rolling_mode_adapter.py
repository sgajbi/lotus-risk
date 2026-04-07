import asyncio

import pytest

from app.contracts.rolling import RollingStatefulInput
from app.services.rolling_mode_adapter import (
    _build_stateful_source_request,
    calculate_rolling_metrics_stateful,
)


class _RecordingLotusPerformanceClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.request_payload: dict[str, object] | None = None
        self.correlation_id: str | None = None

    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        self.request_payload = request_payload
        self.correlation_id = correlation_id
        return self.payload


class _StubLotusCoreClient:
    def __init__(self, *, reporting_currency: str = "USD") -> None:
        self.reporting_currency = reporting_currency
        self.calls: list[dict[str, object]] = []

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "portfolio_id": portfolio_id,
                "request_payload": request_payload,
                "correlation_id": correlation_id,
            }
        )
        return {
            "valuation_context": {
                "portfolio_currency": self.reporting_currency,
                "reporting_currency": self.reporting_currency,
            }
        }


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
    assert selection["include_risk_free"] is True


def test_stateful_adapter_happy_path() -> None:
    client = _RecordingLotusPerformanceClient(
        {
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
                "risk_free_returns": [
                    {"date": "2026-01-02", "return_value": "0.0001"},
                    {"date": "2026-01-03", "return_value": "0.0001"},
                    {"date": "2026-01-04", "return_value": "0.0001"},
                ],
            }
        }
    )
    core_client = _StubLotusCoreClient()

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
    assert core_client.calls[0]["portfolio_id"] == "DEMO_DPM_EUR_001"
    assert response.input_mode.value == "stateful"
    assert "YTD" in response.results


def test_stateful_adapter_requires_series_object() -> None:
    client = _RecordingLotusPerformanceClient({"not_series": {}})
    with pytest.raises(ValueError, match="missing 'series' object"):
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_VOLATILITY"]),
                performance_client=client,
                correlation_id=None,
            )
        )


def test_stateful_adapter_requires_benchmark_when_metric_requested() -> None:
    client = _RecordingLotusPerformanceClient(
        {
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "0.0100"},
                    {"date": "2026-01-03", "return_value": "-0.0200"},
                ]
            }
        }
    )
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
    client = _RecordingLotusPerformanceClient(
        {
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "0.0100"},
                    {"date": "2026-01-03", "return_value": "-0.0200"},
                ]
            }
        }
    )
    with pytest.raises(ValueError, match="no risk-free returns"):
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_SHARPE"]),
                performance_client=client,
                core_client=_StubLotusCoreClient(),
                correlation_id=None,
            )
        )


def test_stateful_adapter_rejects_invalid_return_value() -> None:
    client = _RecordingLotusPerformanceClient(
        {
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
    client = _RecordingLotusPerformanceClient(
        {
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "0.0100"},
                    {"date": "2026-01-03", "return_value": "-0.0200"},
                ],
                "risk_free_returns": [
                    {"date": "2026-01-02", "return_value": "0.0001"},
                    {"date": "2026-01-03", "return_value": "0.0001"},
                ],
            }
        }
    )
    with pytest.raises(ValueError, match="reporting_currency is required for rolling Sharpe"):
        asyncio.run(
            calculate_rolling_metrics_stateful(
                _stateful_input(["ROLLING_SHARPE"]),
                performance_client=client,
                core_client=None,
                correlation_id=None,
            )
        )

