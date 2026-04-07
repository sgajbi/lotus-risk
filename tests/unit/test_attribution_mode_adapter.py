import asyncio
from datetime import date

import pytest

from app.contracts.attribution import HistoricalAttributionStatefulInput
from app.services import attribution_mode_adapter as adapter
from app.services.attribution_mode_adapter import calculate_historical_attribution_stateful
from app.services.stateful_returns_series_parser import (
    decimal_return_to_percentage_points,
    to_return_points,
)
from tests.support.historical_attribution_fakes import (
    RecordingHistoricalAttributionCoreClient,
    build_stateful_attribution_returns_client,
)


class _StubPerformanceClient:
    def __init__(self) -> None:
        self._client = build_stateful_attribution_returns_client()
        self.payload: dict[str, object] | None = None

    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        self.payload = request_payload
        return await self._client.get_returns_series(
            request_payload=request_payload,
            correlation_id=correlation_id,
        )


class _StubCoreClient(RecordingHistoricalAttributionCoreClient):
    def __init__(self) -> None:
        super().__init__()
        self.position_payloads = self.position_calls
        self.enrichment_calls: list[list[str]] = []

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, object]:
        self.enrichment_calls.append(security_ids)
        return {
            "records": [
                {"security_id": "SEC_A", "issuer_id": "ISSUER_A", "issuer_name": "Issuer A"},
                {"security_id": "SEC_B", "issuer_id": "ISSUER_B", "issuer_name": "Issuer B"},
            ]
        }


class _StubCoreClientBadRows(_StubCoreClient):
    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {"rows": "bad"}


class _StubCoreClientNoRows(_StubCoreClient):
    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {"rows": [], "page": {"next_page_token": None}}


class _StubCoreClientInvalidExposure(_StubCoreClient):
    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {
            "rows": [
                {
                    "security_id": "SEC_A",
                    "valuation_date": None,
                    "dimensions": {"sector": "TECH"},
                    "ending_market_value_portfolio_currency": "100",
                }
            ],
            "page": {"next_page_token": None},
        }


class _StubCoreClientBadRecords(_StubCoreClient):
    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {"records": "bad"}


class _StubPerformanceClientMissingSeries(_StubPerformanceClient):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {}


class _StubPerformanceClientEmptyReturns(_StubPerformanceClient):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {"series": {"portfolio_returns": []}}


def _stateful_input(
    *, grouping_dimensions: list[str], attribution_types: list[str]
) -> HistoricalAttributionStatefulInput:
    return HistoricalAttributionStatefulInput.model_validate(
        {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-01-04",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "attribution_options": {
                "attribution_types": attribution_types,
                "metrics": ["VOLATILITY"],
                "grouping_dimensions": grouping_dimensions,
            },
        }
    )


def test_stateful_attribution_total_risk_happy_path() -> None:
    perf = _StubPerformanceClient()
    core = _StubCoreClient()
    response = asyncio.run(
        calculate_historical_attribution_stateful(
            _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
            performance_client=perf,
            core_client=core,
            correlation_id="corr-attr",
        )
    )
    assert perf.payload is not None
    assert perf.payload["input_mode"] == "stateful"
    assert perf.payload["stateful_input"] == {}
    assert perf.payload["window"] == {
        "mode": "EXPLICIT",
        "from_date": "2026-01-01",
        "to_date": "2026-01-04",
    }
    assert len(core.position_payloads) == 1
    first_payload = core.position_payloads[0]["request_payload"]
    assert first_payload["dimensions"] == ["sector"]
    assert response.input_mode.value == "stateful"
    assert response.results["YTD"].error is None


def test_stateful_attribution_asset_class_and_reporting_currency() -> None:
    perf = _StubPerformanceClient()
    core = _StubCoreClient()
    payload = _stateful_input(grouping_dimensions=["ASSET_CLASS"], attribution_types=["TOTAL_RISK"])
    payload.reporting_currency = "USD"
    response = asyncio.run(
        calculate_historical_attribution_stateful(
            payload,
            performance_client=perf,
            core_client=core,
            correlation_id="corr-attr",
        )
    )
    assert response.results["YTD"].error is None
    first_payload = core.position_payloads[0]["request_payload"]
    assert first_payload["dimensions"] == ["asset_class"]
    assert first_payload["reporting_currency"] == "USD"


def test_stateful_attribution_issuer_grouping_uses_enrichment() -> None:
    perf = _StubPerformanceClient()
    core = _StubCoreClient()
    response = asyncio.run(
        calculate_historical_attribution_stateful(
            _stateful_input(grouping_dimensions=["ISSUER"], attribution_types=["TOTAL_RISK"]),
            performance_client=perf,
            core_client=core,
            correlation_id="corr-attr",
        )
    )
    assert len(core.enrichment_calls) == 1
    assert set(core.enrichment_calls[0]) == {"SEC_A", "SEC_B"}
    assert response.results["YTD"].error is None


def test_stateful_attribution_issuer_grouping_rejects_bad_enrichment_shape() -> None:
    with pytest.raises(ValueError, match="enrichment payload missing 'records' list"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["ISSUER"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClient(),
                core_client=_StubCoreClientBadRecords(),
                correlation_id="corr-attr",
            )
        )


def test_stateful_attribution_rejects_active_risk_without_benchmark_exposure_contract() -> None:
    with pytest.raises(ValueError, match="benchmark exposure history contract"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["ACTIVE_RISK"]),
                performance_client=_StubPerformanceClient(),
                core_client=_StubCoreClient(),
                correlation_id="corr-attr",
            )
        )


def test_stateful_attribution_rejects_custom_grouping() -> None:
    with pytest.raises(ValueError, match="grouping_dimension=CUSTOM"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["CUSTOM"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClient(),
                core_client=_StubCoreClient(),
                correlation_id="corr-attr",
            )
        )


def test_stateful_attribution_rejects_missing_series_object() -> None:
    with pytest.raises(ValueError, match="payload missing 'series' object"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClientMissingSeries(),
                core_client=_StubCoreClient(),
                correlation_id="corr-attr",
            )
        )


def test_stateful_attribution_rejects_empty_portfolio_returns() -> None:
    with pytest.raises(ValueError, match="returned no portfolio returns"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClientEmptyReturns(),
                core_client=_StubCoreClient(),
                correlation_id="corr-attr",
            )
        )


def test_stateful_attribution_rejects_missing_rows_list() -> None:
    with pytest.raises(ValueError, match="payload missing 'rows' list"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClient(),
                core_client=_StubCoreClientBadRows(),
                correlation_id="corr-attr",
            )
        )


def test_stateful_attribution_rejects_empty_rows() -> None:
    with pytest.raises(ValueError, match="returned no rows"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClient(),
                core_client=_StubCoreClientNoRows(),
                correlation_id="corr-attr",
            )
        )


def test_stateful_attribution_rejects_empty_exposure_history() -> None:
    with pytest.raises(ValueError, match="unable to build exposure history"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClient(),
                core_client=_StubCoreClientInvalidExposure(),
                correlation_id="corr-attr",
            )
        )


def test_helper_branch_coverage_for_conversion_and_grouping() -> None:
    assert to_return_points("bad") == []
    assert to_return_points(
        [1, {"date": None}, {"date": "2026-01-02", "return_value": "0.01"}]
    )[0].date == date(2026, 1, 2)
    with pytest.raises(ValueError, match="Invalid return value"):
        decimal_return_to_percentage_points("nan%")
    with pytest.raises(ValueError, match="Invalid market value"):
        adapter._as_decimal("invalid")

    row = {"security_id": "SEC_X", "dimensions": {}}
    assert adapter._group_key_and_label(row=row, grouping_dimension="POSITION", issuer_map={}) == (
        "SEC_X",
        "SEC_X",
    )
    assert adapter._group_key_and_label(
        row=row, grouping_dimension="ASSET_CLASS", issuer_map={}
    ) == ("ASSET_CLASS_UNKNOWN", "UNKNOWN")
    assert adapter._group_key_and_label(row=row, grouping_dimension="ISSUER", issuer_map={}) == (
        "ISSUER_SEC_X",
        None,
    )
    with pytest.raises(ValueError, match="Unsupported stateful grouping_dimension"):
        adapter._group_key_and_label(
            row=row,
            grouping_dimension="UNKNOWN",  # type: ignore[arg-type]
            issuer_map={},
        )


def test_build_exposure_points_skips_zero_total_rows() -> None:
    points = adapter._build_exposure_points(
        rows=[
            {
                "security_id": "SEC_ZERO",
                "valuation_date": "2026-01-02",
                "dimensions": {"sector": "TECH"},
                "ending_market_value_portfolio_currency": "0",
            }
        ],
        grouping_dimensions=["SECTOR"],
        issuer_map={},
    )
    assert points == []


def test_build_issuer_map_handles_empty_and_partial_rows() -> None:
    core = _StubCoreClient()
    empty_map = asyncio.run(
        adapter._build_issuer_map(
            core_client=core, rows=[{"security_id": None}], correlation_id="corr"
        )
    )
    assert empty_map == {}

    mixed_map = asyncio.run(
        adapter._build_issuer_map(
            core_client=core,
            rows=[{"security_id": "SEC_A"}],
            correlation_id="corr",
        )
    )
    assert mixed_map["SEC_A"] == ("ISSUER_A", "Issuer A")


def test_build_issuer_map_skips_non_dict_and_missing_security_id_records() -> None:
    class _StubCoreClientWithBadRecords(_StubCoreClient):
        async def get_instrument_enrichment(
            self,
            *,
            security_ids: list[str],
            correlation_id: str | None,
        ) -> dict[str, object]:
            return {
                "records": [
                    "bad_record",
                    {"issuer_id": "ISSUER_ONLY"},
                    {"security_id": "SEC_A", "issuer_id": "ISSUER_A"},
                ]
            }

    issuer_map = asyncio.run(
        adapter._build_issuer_map(
            core_client=_StubCoreClientWithBadRecords(),
            rows=[{"security_id": "SEC_A"}],
            correlation_id="corr",
        )
    )
    assert issuer_map == {"SEC_A": ("ISSUER_A", None)}

