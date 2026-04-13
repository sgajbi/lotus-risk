import asyncio

import pytest

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownStatefulInput,
)
from app.services.drawdown_mode_adapter import (
    calculate_drawdown_stateful,
)
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient


def _stateful() -> DrawdownStatefulInput:
    return DrawdownStatefulInput.model_validate(
        {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-01-08",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "benchmark_policy": {"include_benchmark": True, "missing_benchmark_policy": "REQUIRE"},
        }
    )


def test_drawdown_stateful_adapter_happy_path() -> None:
    client = RecordingLotusPerformanceClient(
        response_payload={
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "0.0100"},
                    {"date": "2026-01-03", "return_value": "-0.0200"},
                ],
                "benchmark_returns": [
                    {"date": "2026-01-02", "return_value": "0.0060"},
                    {"date": "2026-01-03", "return_value": "-0.0100"},
                ],
            }
        }
    )
    response = asyncio.run(
        calculate_drawdown_stateful(
            _stateful(),
            analysis_options=DrawdownAnalysisOptions.model_validate({}),
            performance_client=client,
            correlation_id="corr-dd",
        )
    )
    assert client.request_payload is not None
    assert client.request_payload["input_mode"] == "stateful"
    assert client.request_payload["stateful_input"] == {}
    assert client.request_payload["window"] == {
        "mode": "EXPLICIT",
        "from_date": "2026-01-01",
        "to_date": "2026-01-08",
    }
    assert client.correlation_id == "corr-dd"
    assert "YTD" in response.results
    assert response.metadata.include_benchmark is True
    assert response.metadata.missing_benchmark_policy == "REQUIRE"
    assert response.metadata.top_n_episodes == 5
    assert response.metadata.duration_unit == "BUSINESS_DAYS"
    assert response.metadata.source_services == ["lotus-risk", "lotus-performance"]
    assert response.metadata.request_fingerprint is not None
    assert response.metadata.request_fingerprint.startswith("sha256:")
    assert list(response.metadata.upstream_request_fingerprints) == [
        "lotus-performance:/integration/returns/series"
    ]


def test_drawdown_stateful_adapter_requires_series_payload() -> None:
    client = RecordingLotusPerformanceClient(response_payload={})
    with pytest.raises(ValueError, match="missing 'series' object"):
        asyncio.run(
            calculate_drawdown_stateful(
                _stateful(),
                analysis_options=DrawdownAnalysisOptions.model_validate({}),
                performance_client=client,
                correlation_id=None,
            )
        )


def test_drawdown_stateful_adapter_requires_portfolio_returns() -> None:
    client = RecordingLotusPerformanceClient(response_payload={"series": {"portfolio_returns": []}})
    with pytest.raises(ValueError, match="no portfolio returns"):
        asyncio.run(
            calculate_drawdown_stateful(
                _stateful(),
                analysis_options=DrawdownAnalysisOptions.model_validate({}),
                performance_client=client,
                correlation_id=None,
            )
        )


def test_drawdown_stateful_adapter_requires_benchmark_when_policy_requires() -> None:
    client = RecordingLotusPerformanceClient(
        response_payload={
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "0.0100"},
                    {"date": "2026-01-03", "return_value": "-0.0200"},
                ],
                "benchmark_returns": [],
            }
        }
    )
    with pytest.raises(ValueError, match="no benchmark returns"):
        asyncio.run(
            calculate_drawdown_stateful(
                _stateful(),
                analysis_options=DrawdownAnalysisOptions.model_validate({}),
                performance_client=client,
                correlation_id=None,
            )
        )


def test_drawdown_stateful_adapter_rejects_invalid_portfolio_return_value() -> None:
    client = RecordingLotusPerformanceClient(
        response_payload={
            "series": {
                "portfolio_returns": [
                    {"date": "2026-01-02", "return_value": "bad"},
                ],
            }
        }
    )
    with pytest.raises(ValueError, match="Invalid return value"):
        asyncio.run(
            calculate_drawdown_stateful(
                DrawdownStatefulInput.model_validate(
                    {
                        "portfolio_id": "DEMO_DPM_EUR_001",
                        "as_of_date": "2026-01-02",
                        "periods": [{"type": "YTD"}],
                        "benchmark_policy": {
                            "include_benchmark": False,
                            "missing_benchmark_policy": "IGNORE",
                        },
                    }
                ),
                analysis_options=DrawdownAnalysisOptions.model_validate({}),
                performance_client=client,
                correlation_id=None,
            )
        )


def test_drawdown_stateful_adapter_skips_malformed_rows_and_allows_optional_benchmark() -> None:
    client = RecordingLotusPerformanceClient(
        response_payload={
            "series": {
                "portfolio_returns": [
                    "bad-row",
                    {"date": 123, "return_value": "0.0100"},
                    {"date": "2026-01-02", "return_value": "0.0100"},
                ],
                "benchmark_returns": None,
            }
        }
    )
    response = asyncio.run(
        calculate_drawdown_stateful(
            DrawdownStatefulInput.model_validate(
                {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-02",
                    "periods": [{"type": "YTD"}],
                    "benchmark_policy": {
                        "include_benchmark": False,
                        "missing_benchmark_policy": "IGNORE",
                    },
                }
            ),
            analysis_options=DrawdownAnalysisOptions.model_validate({}),
            performance_client=client,
            correlation_id=None,
        )
    )
    assert "YTD" in response.results
    assert response.metadata.include_benchmark is False
    assert response.metadata.missing_benchmark_policy == "IGNORE"
