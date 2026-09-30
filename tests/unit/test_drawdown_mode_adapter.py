import asyncio

import pytest

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownStatefulInput,
)
from app.services.drawdown_mode_adapter import (
    calculate_drawdown_stateful,
)
from tests.support.downstream_authority import admitted_test_authority
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import build_returns_series_response


def _stateful() -> DrawdownStatefulInput:
    return DrawdownStatefulInput.model_validate(
        {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-01-08",
            "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "benchmark_policy": {"include_benchmark": True, "missing_benchmark_policy": "REQUIRE"},
        }
    )


def test_drawdown_stateful_adapter_happy_path() -> None:
    client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=(("2026-01-02", "0.0100"), ("2026-01-03", "-0.0200")),
            benchmark_returns=(("2026-01-02", "0.0060"), ("2026-01-03", "-0.0100")),
            as_of_date="2026-01-08",
        )
    )
    response = asyncio.run(
        calculate_drawdown_stateful(
            _stateful(),
            analysis_options=DrawdownAnalysisOptions.model_validate({}),
            performance_client=client,
            authority=admitted_test_authority("corr-dd"),
        )
    )
    assert client.request_payload is not None
    assert client.request_payload["input_mode"] == "stateful"
    assert client.request_payload["stateful_input"] == {}
    assert client.request_payload["benchmark"] == {
        "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
        "return_source": "calculated",
    }
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
    assert response.metadata.source_returns_evidence is not None
    assert response.metadata.source_returns_evidence.freshness == "current"


def test_drawdown_stateful_adapter_retains_initial_loss_from_qualified_source() -> None:
    client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=(("2026-01-02", "-0.1000"), ("2026-01-05", "0.0000")),
            as_of_date="2026-01-05",
        )
    )
    response = asyncio.run(
        calculate_drawdown_stateful(
            DrawdownStatefulInput.model_validate(
                {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-05",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                }
            ),
            analysis_options=DrawdownAnalysisOptions.model_validate(
                {"include_underwater_series": True}
            ),
            performance_client=client,
            authority=admitted_test_authority("corr-opening-loss"),
        )
    )
    period = response.results["YTD"]
    assert period.summary is not None
    assert period.summary.max_drawdown == pytest.approx(-0.1)
    assert period.summary.max_drawdown_peak_date is None
    assert period.summary.is_recovered is False
    assert period.underwater_series is not None
    assert [point.drawdown for point in period.underwater_series] == pytest.approx([-0.1, -0.1])
    assert response.metadata.source_returns_evidence is not None
    assert str(response.metadata.source_returns_evidence.calculation_id) == (
        "00000000-0000-4000-8000-000000000001"
    )


def test_drawdown_stateful_adapter_requires_series_payload() -> None:
    client = RecordingLotusPerformanceClient(response_payload={})
    with pytest.raises(ValueError, match="missing 'series' object"):
        asyncio.run(
            calculate_drawdown_stateful(
                _stateful(),
                analysis_options=DrawdownAnalysisOptions.model_validate({}),
                performance_client=client,
                authority=admitted_test_authority(),
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
                authority=admitted_test_authority(),
            )
        )


def test_drawdown_stateful_adapter_requires_benchmark_when_policy_requires() -> None:
    client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=(("2026-01-02", "0.0100"), ("2026-01-03", "-0.0200")),
            benchmark_returns=(),
            as_of_date="2026-01-08",
        )
    )
    with pytest.raises(ValueError, match="no benchmark returns"):
        asyncio.run(
            calculate_drawdown_stateful(
                _stateful(),
                analysis_options=DrawdownAnalysisOptions.model_validate({}),
                performance_client=client,
                authority=admitted_test_authority(),
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
                authority=admitted_test_authority(),
            )
        )


def test_drawdown_stateful_adapter_skips_malformed_rows_and_allows_optional_benchmark() -> None:
    client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=(("2026-01-02", "0.0100"),),
            as_of_date="2026-01-02",
        )
    )
    client.response_payload["series"]["portfolio_returns"] = [
        "bad-row",
        {"date": 123, "return_value": "0.0100"},
        {"date": "2026-01-02", "return_value": "0.0100"},
    ]
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
            authority=admitted_test_authority(),
        )
    )
    assert "YTD" in response.results
    assert response.metadata.include_benchmark is False
    assert response.metadata.missing_benchmark_policy == "IGNORE"


def test_drawdown_stateful_preserves_changed_performance_identity_for_same_numbers() -> None:
    common_rows = (("2026-01-02", "0.0100"), ("2026-01-05", "-0.0200"))
    baseline = asyncio.run(
        calculate_drawdown_stateful(
            DrawdownStatefulInput.model_validate(
                {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-05",
                    "periods": [{"type": "YTD"}],
                }
            ),
            analysis_options=DrawdownAnalysisOptions.model_validate({}),
            performance_client=RecordingLotusPerformanceClient(
                response_payload=build_returns_series_response(portfolio_returns=common_rows)
            ),
            authority=admitted_test_authority(),
        )
    )
    corrected = asyncio.run(
        calculate_drawdown_stateful(
            DrawdownStatefulInput.model_validate(
                {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-05",
                    "periods": [{"type": "YTD"}],
                }
            ),
            analysis_options=DrawdownAnalysisOptions.model_validate({}),
            performance_client=RecordingLotusPerformanceClient(
                response_payload=build_returns_series_response(
                    portfolio_returns=common_rows,
                    calculation_id="00000000-0000-4000-8000-000000000002",
                    calculation_hash="sha256:" + "3" * 64,
                )
            ),
            authority=admitted_test_authority(),
        )
    )

    assert baseline.metadata.request_fingerprint == corrected.metadata.request_fingerprint
    assert baseline.results == corrected.results
    assert baseline.metadata.source_returns_evidence is not None
    assert corrected.metadata.source_returns_evidence is not None
    assert (
        baseline.metadata.source_returns_evidence.calculation_id
        != corrected.metadata.source_returns_evidence.calculation_id
    )
    assert (
        baseline.metadata.source_returns_evidence.calculation_hash
        != corrected.metadata.source_returns_evidence.calculation_hash
    )
