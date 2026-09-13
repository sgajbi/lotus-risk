import asyncio
import copy
from datetime import date
from typing import Any, cast

import pytest

from app.contracts.attribution import (
    ExposurePoint,
    GroupingDimension,
    HistoricalAttributionResponse,
    HistoricalAttributionStatefulInput,
)
from app.contracts.downstream_authority import DownstreamAuthority
from app.services.attribution_exposure_history import (
    as_decimal,
    build_exposure_points,
    build_issuer_map,
    group_key_and_label,
)
from app.services.attribution_mode_adapter import calculate_historical_attribution_stateful
from app.services.attribution_stateful_inputs import _expected_group_key_by_source_key
from app.services.stateful_returns_series_parser import (
    decimal_return_to_percentage_points,
    to_return_points,
)
from app.upstream_errors import UpstreamServiceError
from tests.support.downstream_authority import admitted_test_authority
from tests.support.historical_attribution_fakes import (
    RecordingHistoricalAttributionCoreClient,
    build_benchmark_exposure_context_response,
    build_stateful_attribution_returns_client,
)


class _StubPerformanceClient:
    def __init__(self, *, contribution_response: dict[str, Any] | None = None) -> None:
        self._client = build_stateful_attribution_returns_client()
        self._client.contribution_response = contribution_response
        self.payload: dict[str, object] | None = None

    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, object],
        authority: DownstreamAuthority,
    ) -> dict[str, object]:
        self.payload = request_payload
        return await self._client.get_returns_series(
            request_payload=request_payload,
            authority=authority,
        )

    async def get_contribution(
        self,
        *,
        request_payload: dict[str, object],
        authority: DownstreamAuthority,
    ) -> dict[str, object]:
        return await self._client.get_contribution(
            request_payload=request_payload,
            authority=authority,
        )

    async def get_benchmark_exposure_context(
        self,
        *,
        request_payload: dict[str, object],
        authority: DownstreamAuthority,
    ) -> dict[str, object]:
        return await self._client.get_benchmark_exposure_context(
            request_payload=request_payload,
            authority=authority,
        )

    @property
    def benchmark_exposure_context_calls(self) -> list[dict[str, object]]:
        return self._client.benchmark_exposure_context_calls

    @property
    def contribution_calls(self) -> list[dict[str, Any]]:
        return self._client.contribution_calls


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
        authority: DownstreamAuthority,
    ) -> dict[str, object]:
        return {"rows": "bad"}


class _StubCoreClientNoRows(_StubCoreClient):
    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        authority: DownstreamAuthority,
    ) -> dict[str, object]:
        return {"rows": [], "page": {"next_page_token": None}}


class _StubCoreClientInvalidExposure(_StubCoreClient):
    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        authority: DownstreamAuthority,
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
        authority: DownstreamAuthority,
    ) -> dict[str, object]:
        return {}


class _StubPerformanceClientEmptyReturns(_StubPerformanceClient):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, object],
        authority: DownstreamAuthority,
    ) -> dict[str, object]:
        return {"series": {"portfolio_returns": []}}


def _stateful_input(
    *,
    grouping_dimensions: list[str],
    attribution_types: list[str],
    metrics: list[str] | None = None,
) -> HistoricalAttributionStatefulInput:
    return HistoricalAttributionStatefulInput.model_validate(
        {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-01-06",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "attribution_options": {
                "attribution_types": attribution_types,
                "metrics": metrics or ["VOLATILITY"],
                "grouping_dimensions": grouping_dimensions,
            },
        }
    )


def _empirical_sector_contribution_response(*, tech_adjustment_pp: float = 0.0) -> dict[str, Any]:
    dates = ["2026-01-02", "2026-01-05", "2026-01-06"]
    portfolio_pp = [1.0, -0.5, 0.4]
    tech_weights = [0.60, 0.65, 0.65]
    health_weights = [0.40, 0.35, 0.35]
    tech_returns = [value + tech_adjustment_pp for value in portfolio_pp]
    health_returns = [
        (portfolio - tech_weight * tech_return) / health_weight
        for portfolio, tech_weight, health_weight, tech_return in zip(
            portfolio_pp,
            tech_weights,
            health_weights,
            tech_returns,
            strict=True,
        )
    ]

    def row(group: str, weights: list[float], returns: list[float]) -> dict[str, Any]:
        return {
            "key": {"sector": group},
            "is_other": False,
            "group_return": {
                "status": "READY",
                "currency": "USD",
                "return_basis": "SOURCE_POSITION_VALUATION_TWR",
                "weight_basis": "BEGINNING_CAPITAL_RATIO",
                "series": [
                    {
                        "date": day,
                        "return_pct": return_pp,
                        "portfolio_weight_pct": weight * 100.0,
                    }
                    for day, weight, return_pp in zip(dates, weights, returns, strict=True)
                ],
            },
        }

    return {
        "results_by_period": {
            "EXPLICIT": {
                "levels": [
                    {
                        "name": "sector",
                        "rows": [
                            row("TECH", tech_weights, tech_returns),
                            row("HEALTH", health_weights, health_returns),
                        ],
                    }
                ]
            }
        }
    }


@pytest.mark.parametrize(
    ("grouping_dimension", "classified_key", "unknown_key"),
    [
        ("SECTOR", "SECTOR_TECH", "SECTOR_UNKNOWN"),
        ("ASSET_CLASS", "ASSET_CLASS_EQUITY", "ASSET_CLASS_UNKNOWN"),
    ],
)
def test_core_unknown_group_accepts_only_the_producer_unclassified_alias(
    grouping_dimension: GroupingDimension,
    classified_key: str,
    unknown_key: str,
) -> None:
    points = [
        ExposurePoint(
            date=date(2026, 1, 2),
            grouping_dimension=grouping_dimension,
            group_key=classified_key,
            group_label="TECH" if grouping_dimension == "SECTOR" else "EQUITY",
            weight=0.6,
        ),
        ExposurePoint(
            date=date(2026, 1, 2),
            grouping_dimension=grouping_dimension,
            group_key=unknown_key,
            group_label="UNKNOWN",
            weight=0.4,
        ),
    ]

    mapping = _expected_group_key_by_source_key(
        exposure_history=points,
        grouping_dimension=grouping_dimension,
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 2),
    )

    assert mapping == {
        "TECH" if grouping_dimension == "SECTOR" else "EQUITY": classified_key,
        "UNKNOWN": unknown_key,
        "Unclassified": unknown_key,
    }

    points.append(
        ExposurePoint(
            date=date(2026, 1, 2),
            grouping_dimension=grouping_dimension,
            group_key=f"{grouping_dimension}_LITERAL_UNCLASSIFIED",
            group_label="Unclassified",
            weight=0.0,
        )
    )
    with pytest.raises(UpstreamServiceError) as excinfo:
        _expected_group_key_by_source_key(
            exposure_history=points,
            grouping_dimension=grouping_dimension,
            start_date=date(2026, 1, 2),
            end_date=date(2026, 1, 2),
        )
    assert excinfo.value.code == "UPSTREAM_INVALID_RESPONSE"


def test_stateful_attribution_total_risk_happy_path() -> None:
    perf = _StubPerformanceClient()
    core = _StubCoreClient()
    response = asyncio.run(
        calculate_historical_attribution_stateful(
            _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
            performance_client=perf,
            core_client=core,
            authority=admitted_test_authority("corr-attr"),
        )
    )
    assert perf.payload is not None
    assert perf.payload["input_mode"] == "stateful"
    assert perf.payload["stateful_input"] == {}
    assert perf.payload["window"] == {
        "mode": "EXPLICIT",
        "from_date": "2026-01-01",
        "to_date": "2026-01-06",
    }
    assert len(core.position_payloads) == 1
    first_payload = core.position_payloads[0]["request_payload"]
    assert first_payload["dimensions"] == ["sector"]
    assert response.input_mode.value == "stateful"
    assert response.results["YTD"].error is None
    assert response.metadata.source_services == [
        "lotus-risk",
        "lotus-performance",
        "lotus-core",
    ]
    assert response.metadata.request_fingerprint is not None
    assert response.metadata.request_fingerprint.startswith("sha256:")
    assert set(response.metadata.upstream_request_fingerprints) == {
        "lotus-performance:/integration/returns/series",
        "lotus-performance:/performance/contribution",
    }


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
            authority=admitted_test_authority("corr-attr"),
        )
    )
    assert response.results["YTD"].error is None
    first_payload = core.position_payloads[0]["request_payload"]
    assert first_payload["dimensions"] == ["asset_class"]
    assert first_payload["reporting_currency"] == "USD"


def test_stateful_contribution_uses_core_reporting_values_not_unowned_fx() -> None:
    """Risk requests BASE_ONLY when Core owns the reporting-currency valuations.

    ``BOTH`` is Performance's local/FX decomposition contract and rejects a
    mixed-currency book without supplied rates.  Risk has neither rates nor
    authority to invent them, so its request must preserve the producer's
    source-owned valuation path and the selected NET/GROSS basis.
    """
    performance_client = _StubPerformanceClient()
    stateful = _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"])
    stateful.reporting_currency = "USD"

    asyncio.run(
        calculate_historical_attribution_stateful(
            stateful,
            performance_client=performance_client,
            core_client=_StubCoreClient(),
            authority=admitted_test_authority("corr-mixed-currency"),
        )
    )

    contribution_request = performance_client.contribution_calls[0]["request_payload"]
    assert contribution_request["report_ccy"] == "USD"
    assert contribution_request["currency_mode"] == "BASE_ONLY"
    assert "fx" not in contribution_request
    stateful_input = contribution_request["stateful_input"]
    assert stateful_input["metric_basis"] == "NET"
    assert contribution_request["hierarchy"] == ["sector"]
    assert performance_client.contribution_calls[0]["tenant_id"] == "tenant-a"


def test_stateful_lineage_fingerprints_every_contribution_request_and_evidence() -> None:
    """Requests and used observations have separate, deterministic identities."""
    baseline_client = _StubPerformanceClient(
        contribution_response=_empirical_sector_contribution_response()
    )
    changed_client = _StubPerformanceClient(
        contribution_response=_empirical_sector_contribution_response(tech_adjustment_pp=0.1)
    )
    shuffled_response = copy.deepcopy(_empirical_sector_contribution_response())
    levels = shuffled_response["results_by_period"]["EXPLICIT"]["levels"]
    rows = levels[0]["rows"]
    rows.reverse()
    for row in rows:
        row["group_return"]["series"].reverse()
    shuffled_client = _StubPerformanceClient(contribution_response=shuffled_response)

    def calculate(
        performance_client: _StubPerformanceClient,
        correlation_id: str,
    ) -> HistoricalAttributionResponse:
        return asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=performance_client,
                core_client=_StubCoreClient(),
                authority=admitted_test_authority(correlation_id),
            )
        )

    baseline = calculate(baseline_client, "corr-evidence-a")
    changed = calculate(changed_client, "corr-evidence-b")
    shuffled = calculate(shuffled_client, "corr-evidence-c")

    assert baseline.results["YTD"].attribution_sets[0].risk_basis == "empirical_group_returns"
    assert changed.metadata.request_fingerprint != baseline.metadata.request_fingerprint
    assert shuffled.metadata.request_fingerprint == baseline.metadata.request_fingerprint
    contribution_operation = "lotus-performance:/performance/contribution"
    assert (
        baseline.metadata.upstream_request_fingerprints[contribution_operation]
        == changed.metadata.upstream_request_fingerprints[contribution_operation]
        == shuffled.metadata.upstream_request_fingerprints[contribution_operation]
    )
    # Distinct admitted authorities do not enter reproducibility fingerprints.
    assert (
        baseline.metadata.upstream_request_fingerprints
        == shuffled.metadata.upstream_request_fingerprints
    )


def test_stateful_lineage_excludes_degraded_observations_unused_by_covariance() -> None:
    def degraded_response(*, tech_adjustment_pp: float) -> dict[str, Any]:
        response = _empirical_sector_contribution_response(tech_adjustment_pp=tech_adjustment_pp)
        levels = response["results_by_period"]["EXPLICIT"]["levels"]
        health_row = levels[0]["rows"][1]
        health_row["group_return"] = {
            "status": "UNAVAILABLE",
            "currency": None,
            "series": [],
            "reason": "SOURCE_POSITION_VALUATION_ECONOMICS_INCOMPLETE",
        }
        return response

    def calculate(tech_adjustment_pp: float) -> HistoricalAttributionResponse:
        return asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClient(
                    contribution_response=degraded_response(tech_adjustment_pp=tech_adjustment_pp)
                ),
                core_client=_StubCoreClient(),
                authority=admitted_test_authority("corr-degraded-evidence"),
            )
        )

    baseline = calculate(0.0)
    changed_unused_observations = calculate(0.5)

    assert baseline.results["YTD"].attribution_sets[0].risk_basis == "weight_proxy"
    assert (
        changed_unused_observations.results["YTD"].attribution_sets[0].risk_basis == "weight_proxy"
    )
    assert (
        baseline.metadata.request_fingerprint
        == changed_unused_observations.metadata.request_fingerprint
    )
    assert (
        baseline.metadata.upstream_request_fingerprints
        == changed_unused_observations.metadata.upstream_request_fingerprints
    )


def test_unsupported_total_risk_metric_neither_requests_nor_fingerprints_group_observations() -> (
    None
):
    def calculate(
        tech_adjustment_pp: float,
    ) -> tuple[HistoricalAttributionResponse, _StubPerformanceClient]:
        performance_client = _StubPerformanceClient(
            contribution_response=_empirical_sector_contribution_response(
                tech_adjustment_pp=tech_adjustment_pp
            )
        )
        response = asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(
                    grouping_dimensions=["SECTOR"],
                    attribution_types=["TOTAL_RISK"],
                    metrics=["TRACKING_ERROR"],
                ),
                performance_client=performance_client,
                core_client=_StubCoreClient(),
                authority=admitted_test_authority("corr-unsupported-total-risk"),
            )
        )
        return response, performance_client

    baseline, baseline_client = calculate(0.0)
    changed, changed_client = calculate(0.5)

    for response in (baseline, changed):
        attribution_set = response.results["YTD"].attribution_sets[0]
        assert attribution_set.contributors == []
        assert attribution_set.quality_flags == ["metric:TRACKING_ERROR:unsupported_for_total_risk"]
    assert baseline_client.contribution_calls == []
    assert changed_client.contribution_calls == []
    assert baseline.metadata.request_fingerprint == changed.metadata.request_fingerprint
    assert "lotus-performance:/performance/contribution" not in (
        baseline.metadata.upstream_request_fingerprints
    )


def test_mixed_total_risk_metrics_consume_and_fingerprint_only_volatility_evidence() -> None:
    def calculate(
        tech_adjustment_pp: float,
    ) -> tuple[HistoricalAttributionResponse, _StubPerformanceClient]:
        performance_client = _StubPerformanceClient(
            contribution_response=_empirical_sector_contribution_response(
                tech_adjustment_pp=tech_adjustment_pp
            )
        )
        response = asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(
                    grouping_dimensions=["SECTOR"],
                    attribution_types=["TOTAL_RISK"],
                    metrics=["VOLATILITY", "TRACKING_ERROR"],
                ),
                performance_client=performance_client,
                core_client=_StubCoreClient(),
                authority=admitted_test_authority("corr-mixed-total-risk"),
            )
        )
        return response, performance_client

    baseline, baseline_client = calculate(0.0)
    changed, changed_client = calculate(0.5)

    assert len(baseline_client.contribution_calls) == len(changed_client.contribution_calls) == 1
    baseline_sets = baseline.results["YTD"].attribution_sets
    changed_sets = changed.results["YTD"].attribution_sets
    assert [(item.metric, item.risk_basis) for item in baseline_sets] == [
        ("VOLATILITY", "empirical_group_returns"),
        ("TRACKING_ERROR", "weight_proxy"),
    ]
    assert [(item.metric, item.risk_basis) for item in changed_sets] == [
        ("VOLATILITY", "empirical_group_returns"),
        ("TRACKING_ERROR", "weight_proxy"),
    ]
    assert baseline_sets[1].contributors == changed_sets[1].contributors == []
    assert baseline.metadata.request_fingerprint != changed.metadata.request_fingerprint
    contribution_operation = "lotus-performance:/performance/contribution"
    assert (
        baseline.metadata.upstream_request_fingerprints[contribution_operation]
        == changed.metadata.upstream_request_fingerprints[contribution_operation]
    )


def test_active_risk_proxy_does_not_request_or_fingerprint_portfolio_group_returns() -> None:
    performance_client = _StubPerformanceClient(
        contribution_response=_empirical_sector_contribution_response()
    )
    response = asyncio.run(
        calculate_historical_attribution_stateful(
            _stateful_input(
                grouping_dimensions=["SECTOR"],
                attribution_types=["ACTIVE_RISK"],
                metrics=["TRACKING_ERROR"],
            ),
            performance_client=performance_client,
            core_client=_StubCoreClient(),
            authority=admitted_test_authority("corr-active-risk-lineage"),
        )
    )

    active_set = response.results["YTD"].attribution_sets[0]
    assert active_set.risk_basis == "weight_proxy"
    assert performance_client.contribution_calls == []
    assert "lotus-performance:/performance/contribution" not in (
        response.metadata.upstream_request_fingerprints
    )


def test_stateful_lineage_aggregates_all_period_dimension_contribution_requests() -> None:
    payload = _stateful_input(
        grouping_dimensions=["SECTOR", "ASSET_CLASS"], attribution_types=["TOTAL_RISK"]
    )
    payload = HistoricalAttributionStatefulInput.model_validate(
        {
            **payload.model_dump(mode="json"),
            "periods": [
                {
                    "type": "EXPLICIT",
                    "name": "EARLY",
                    "from_date": "2026-01-02",
                    "to_date": "2026-01-05",
                },
                {
                    "type": "EXPLICIT",
                    "name": "LATE",
                    "from_date": "2026-01-05",
                    "to_date": "2026-01-06",
                },
            ],
        }
    )
    performance_client = _StubPerformanceClient()
    response = asyncio.run(
        calculate_historical_attribution_stateful(
            payload,
            performance_client=performance_client,
            core_client=_StubCoreClient(),
            authority=admitted_test_authority("corr-request-set"),
        )
    )

    assert len(performance_client.contribution_calls) == 4
    requests = [call["request_payload"] for call in performance_client.contribution_calls]
    assert {tuple(request["hierarchy"]) for request in requests} == {
        ("sector",),
        ("asset_class",),
    }
    assert {(request["report_start_date"], request["report_end_date"]) for request in requests} == {
        ("2026-01-02", "2026-01-05"),
        ("2026-01-05", "2026-01-06"),
    }
    assert (
        "lotus-performance:/performance/contribution"
        in response.metadata.upstream_request_fingerprints
    )


def test_stateful_attribution_issuer_grouping_uses_enrichment() -> None:
    perf = _StubPerformanceClient()
    core = _StubCoreClient()
    response = asyncio.run(
        calculate_historical_attribution_stateful(
            _stateful_input(grouping_dimensions=["ISSUER"], attribution_types=["TOTAL_RISK"]),
            performance_client=perf,
            core_client=core,
            authority=admitted_test_authority("corr-attr"),
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
                authority=admitted_test_authority("corr-attr"),
            )
        )


def test_stateful_attribution_active_risk_sources_performance_benchmark_exposure_context() -> None:
    perf = _StubPerformanceClient()
    core = _StubCoreClient()
    response = asyncio.run(
        calculate_historical_attribution_stateful(
            _stateful_input(
                grouping_dimensions=["SECTOR"],
                attribution_types=["ACTIVE_RISK"],
                metrics=["TRACKING_ERROR"],
            ),
            performance_client=perf,
            core_client=core,
            authority=admitted_test_authority("corr-attr-active"),
        )
    )

    assert perf.payload is not None
    series_selection = cast(dict[str, Any], perf.payload["series_selection"])
    assert series_selection["include_benchmark"] is True
    exposure_payload = perf.benchmark_exposure_context_calls[0]["request_payload"]
    assert exposure_payload == {
        "portfolio_id": "DEMO_DPM_EUR_001",
        "as_of_date": "2026-01-06",
        "window": {"start_date": "2026-01-02", "end_date": "2026-01-06"},
        "frequency": "DAILY",
        "grouping_dimensions": ["SECTOR"],
        "page": {"page_size": 1000, "page_token": None},
    }
    assert not hasattr(core, "get_benchmark_market_series")
    active_set = response.results["YTD"].attribution_sets[0]
    assert active_set.attribution_type == "ACTIVE_RISK"
    assert active_set.metric == "TRACKING_ERROR"
    assert active_set.contributors


def test_stateful_attribution_rejects_active_risk_when_benchmark_returns_missing() -> None:
    class _NoBenchmarkPerformanceClient(_StubPerformanceClient):
        async def get_returns_series(
            self,
            *,
            request_payload: dict[str, object],
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            self.payload = request_payload
            return {
                "series": {"portfolio_returns": [{"date": "2026-01-02", "return_value": "0.010"}]}
            }

    with pytest.raises(ValueError, match="no benchmark returns"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(
                    grouping_dimensions=["SECTOR"],
                    attribution_types=["ACTIVE_RISK"],
                    metrics=["TRACKING_ERROR"],
                ),
                performance_client=_NoBenchmarkPerformanceClient(),
                core_client=_StubCoreClient(),
                authority=admitted_test_authority("corr-attr"),
            )
        )


def test_stateful_attribution_supports_active_risk_issuer_grouping() -> None:
    class _IssuerBenchmarkPerformanceClient(_StubPerformanceClient):
        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            self._client.benchmark_exposure_context_calls.append(
                {
                    "request_payload": request_payload,
                    "tenant_id": authority.tenant_id,
                    "correlation_id": authority.correlation_id,
                }
            )
            return build_benchmark_exposure_context_response(grouping_dimension="ISSUER")

    performance_client = _IssuerBenchmarkPerformanceClient()
    core_client = _StubCoreClient()

    response = asyncio.run(
        calculate_historical_attribution_stateful(
            _stateful_input(
                grouping_dimensions=["ISSUER"],
                attribution_types=["ACTIVE_RISK"],
                metrics=["TRACKING_ERROR"],
            ),
            performance_client=performance_client,
            core_client=core_client,
            authority=admitted_test_authority("corr-attr"),
        )
    )

    assert response.metadata.requested_grouping_dimensions == ["ISSUER"]
    assert response.metadata.stateful_active_risk_supported_grouping_dimensions == [
        "POSITION",
        "SECTOR",
        "ASSET_CLASS",
        "ISSUER",
    ]
    assert response.metadata.stateful_active_risk_gated_grouping_dimensions == []
    assert core_client.enrichment_calls == [["SEC_A", "SEC_B"]]
    benchmark_context_request = performance_client.benchmark_exposure_context_calls[0][
        "request_payload"
    ]
    assert isinstance(benchmark_context_request, dict)
    assert benchmark_context_request["grouping_dimensions"] == ["ISSUER"]


def test_stateful_attribution_rejects_benchmark_exposure_date_misalignment() -> None:
    class _MisalignedBenchmarkExposurePerformanceClient(_StubPerformanceClient):
        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            payload = build_benchmark_exposure_context_response()
            rows = payload["rows"]
            assert isinstance(rows, list)
            return {
                **payload,
                "rows": [row for row in rows if row.get("valuation_date") != "2026-01-06"],
            }

    with pytest.raises(ValueError, match="missing rows for benchmark return dates: 2026-01-06"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(
                    grouping_dimensions=["SECTOR"],
                    attribution_types=["ACTIVE_RISK"],
                    metrics=["TRACKING_ERROR"],
                ),
                performance_client=_MisalignedBenchmarkExposurePerformanceClient(),
                core_client=_StubCoreClient(),
                authority=admitted_test_authority("corr-attr"),
            )
        )


def test_stateful_attribution_rejects_bad_benchmark_exposure_context_shape() -> None:
    class _BadBenchmarkExposurePerformanceClient(_StubPerformanceClient):
        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            return {**build_benchmark_exposure_context_response(), "rows": "bad"}

    with pytest.raises(ValueError, match="benchmark exposure context payload missing 'rows' list"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(
                    grouping_dimensions=["SECTOR"],
                    attribution_types=["ACTIVE_RISK"],
                    metrics=["TRACKING_ERROR"],
                ),
                performance_client=_BadBenchmarkExposurePerformanceClient(),
                core_client=_StubCoreClient(),
                authority=admitted_test_authority("corr-attr"),
            )
        )


def test_stateful_attribution_rejects_missing_benchmark_exposure_lineage() -> None:
    class _BadLineagePerformanceClient(_StubPerformanceClient):
        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            return {**build_benchmark_exposure_context_response(), "metadata": {}}

    with pytest.raises(ValueError, match="lotus-core lineage"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(
                    grouping_dimensions=["SECTOR"],
                    attribution_types=["ACTIVE_RISK"],
                    metrics=["TRACKING_ERROR"],
                ),
                performance_client=_BadLineagePerformanceClient(),
                core_client=_StubCoreClient(),
                authority=admitted_test_authority("corr-attr"),
            )
        )


def test_stateful_attribution_rejects_custom_grouping() -> None:
    with pytest.raises(ValueError, match="grouping_dimension=CUSTOM"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["CUSTOM"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClient(),
                core_client=_StubCoreClient(),
                authority=admitted_test_authority("corr-attr"),
            )
        )


def test_stateful_attribution_rejects_missing_series_object() -> None:
    with pytest.raises(ValueError, match="payload missing 'series' object"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClientMissingSeries(),
                core_client=_StubCoreClient(),
                authority=admitted_test_authority("corr-attr"),
            )
        )


def test_stateful_attribution_rejects_empty_portfolio_returns() -> None:
    with pytest.raises(ValueError, match="returned no portfolio returns"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClientEmptyReturns(),
                core_client=_StubCoreClient(),
                authority=admitted_test_authority("corr-attr"),
            )
        )


def test_stateful_attribution_rejects_missing_rows_list() -> None:
    with pytest.raises(ValueError, match="payload missing 'rows' list"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClient(),
                core_client=_StubCoreClientBadRows(),
                authority=admitted_test_authority("corr-attr"),
            )
        )


def test_stateful_attribution_rejects_empty_rows() -> None:
    with pytest.raises(ValueError, match="returned no rows"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClient(),
                core_client=_StubCoreClientNoRows(),
                authority=admitted_test_authority("corr-attr"),
            )
        )


def test_stateful_attribution_rejects_empty_exposure_history() -> None:
    with pytest.raises(ValueError, match="unable to build exposure history"):
        asyncio.run(
            calculate_historical_attribution_stateful(
                _stateful_input(grouping_dimensions=["SECTOR"], attribution_types=["TOTAL_RISK"]),
                performance_client=_StubPerformanceClient(),
                core_client=_StubCoreClientInvalidExposure(),
                authority=admitted_test_authority("corr-attr"),
            )
        )


def test_helper_branch_coverage_for_conversion_and_grouping() -> None:
    assert to_return_points("bad") == []
    assert to_return_points([1, {"date": None}, {"date": "2026-01-02", "return_value": "0.01"}])[
        0
    ].date == date(2026, 1, 2)
    with pytest.raises(ValueError, match="Invalid return value"):
        decimal_return_to_percentage_points("nan%")
    with pytest.raises(ValueError, match="Invalid market value"):
        as_decimal("invalid")

    row = {"security_id": "SEC_X", "dimensions": {}}
    assert group_key_and_label(row=row, grouping_dimension="POSITION", issuer_map={}) == (
        "SEC_X",
        "SEC_X",
    )
    assert group_key_and_label(row=row, grouping_dimension="ASSET_CLASS", issuer_map={}) == (
        "ASSET_CLASS_UNKNOWN",
        "UNKNOWN",
    )
    assert group_key_and_label(row=row, grouping_dimension="ISSUER", issuer_map={}) == (
        "ISSUER_SEC_X",
        None,
    )
    with pytest.raises(ValueError, match="Unsupported stateful grouping_dimension"):
        group_key_and_label(
            row=row,
            grouping_dimension="UNKNOWN",  # type: ignore[arg-type]
            issuer_map={},
        )


def test_build_exposure_points_skips_zero_total_rows() -> None:
    points = build_exposure_points(
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
        build_issuer_map(core_client=core, rows=[{"security_id": None}], correlation_id="corr")
    )
    assert empty_map == {}

    mixed_map = asyncio.run(
        build_issuer_map(
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
        build_issuer_map(
            core_client=_StubCoreClientWithBadRecords(),
            rows=[{"security_id": "SEC_A"}],
            correlation_id="corr",
        )
    )
    assert issuer_map == {"SEC_A": ("ISSUER_A", None)}


def test_validate_stateful_groupings_refuses_custom_for_direct_service_callers() -> None:
    """The HTTP contract already rejects CUSTOM at validation (422); this seam guards
    non-route callers of the stateful resolver with the same rule."""
    from app.services.attribution_stateful_inputs import validate_stateful_groupings

    validate_stateful_groupings(["SECTOR", "ASSET_CLASS"])
    with pytest.raises(ValueError, match="grouping_dimension=CUSTOM"):
        validate_stateful_groupings(["CUSTOM"])
