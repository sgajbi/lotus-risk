import pytest
from fastapi.testclient import TestClient

from app.contracts.downstream_authority import DownstreamAuthority
from app.main import app
from app.observability_contracts import RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS
from app.upstream_errors import UpstreamServiceError
from tests.support.app_runtime import override_app_runtime
from tests.support.historical_attribution_fakes import (
    RecordingHistoricalAttributionCoreClient,
    build_benchmark_exposure_context_response,
    build_sector_position_timeseries_rows,
    build_stateful_attribution_returns_client,
    build_stateless_attribution_payload,
)

_EXPECTED_SUPPORTABILITY_METRIC_LABELS = list(RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS)


def test_historical_attribution_stateless_happy_path() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/historical-attribution",
        json=build_stateless_attribution_payload(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_service"] == "lotus-risk"
    assert body["input_mode"] == "stateless"
    assert body["metadata"]["requested_attribution_types"] == ["TOTAL_RISK", "ACTIVE_RISK"]
    assert body["metadata"]["requested_metrics"] == ["VOLATILITY", "TRACKING_ERROR"]
    assert body["metadata"]["requested_grouping_dimensions"] == ["SECTOR"]
    assert body["metadata"]["min_observations_policy"] == "STRICT"
    assert body["metadata"]["stateful_active_risk_supported_grouping_dimensions"] == [
        "POSITION",
        "SECTOR",
        "ASSET_CLASS",
        "ISSUER",
    ]
    assert body["metadata"]["stateful_active_risk_gated_grouping_dimensions"] == []
    assert body["metadata"]["stateful_active_risk_gate_reason"] == "none"
    assert body["metadata"]["calculation_supportability"] == {
        "state": "degraded",
        "reason": "group_return_series_unavailable",
        "freshness_bucket": "current",
        "metric_labels": _EXPECTED_SUPPORTABILITY_METRIC_LABELS,
        # 0, not 4 (#293): four attribution sets were produced and none failed.
        "degraded_metric_count": 0,
        "empty_period_count": 0,
        "evaluated_period_count": 1,
    }
    assert "YTD" in body["results"]
    ytd = body["results"]["YTD"]
    assert ytd["error"] is None
    assert len(ytd["attribution_sets"]) == 4


def test_historical_attribution_supportability_marks_empty_returns() -> None:
    client = TestClient(app)
    payload = build_stateless_attribution_payload()
    payload["stateless_input"]["returns"] = []  # type: ignore[index]
    response = client.post(
        "/analytics/risk/historical-attribution",
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["calculation_supportability"] == {
        "state": "empty",
        "reason": "no_return_observations",
        "freshness_bucket": "unknown",
        "metric_labels": _EXPECTED_SUPPORTABILITY_METRIC_LABELS,
        "degraded_metric_count": 0,
        "empty_period_count": 0,
        "evaluated_period_count": 0,
    }


def test_historical_attribution_stateful_total_risk_happy_path() -> None:
    performance_client = build_stateful_attribution_returns_client()
    core_client = RecordingHistoricalAttributionCoreClient()
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-stateful", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["TOTAL_RISK"],
                        "metrics": ["VOLATILITY"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateful"
    assert body["metadata"]["requested_attribution_types"] == ["TOTAL_RISK"]
    assert body["metadata"]["requested_metrics"] == ["VOLATILITY"]
    assert body["metadata"]["requested_grouping_dimensions"] == ["SECTOR"]
    assert body["metadata"]["min_observations_policy"] == "STRICT"
    assert body["results"]["YTD"]["error"] is None
    assert performance_client.calls == [
        {
            "request_payload": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-06",
                "input_mode": "stateful",
                "stateful_input": {},
                "metric_basis": "NET",
                "window": {
                    "mode": "EXPLICIT",
                    "from_date": "2026-01-01",
                    "to_date": "2026-01-06",
                },
                "frequency": "DAILY",
                "reporting_currency": None,
                "series_selection": {
                    "include_portfolio": True,
                    "include_benchmark": False,
                    "include_risk_free": False,
                },
                "data_policy": {
                    "missing_data_policy": "ALLOW_PARTIAL",
                    "fill_method": "NONE",
                    "calendar_policy": "BUSINESS",
                },
            },
            "tenant_id": "tenant-a",
            "correlation_id": "corr-attr-stateful",
        }
    ]


def test_historical_attribution_stateful_total_risk_aligns_exposure_to_return_dates() -> None:
    performance_client = build_stateful_attribution_returns_client()
    core_rows: list[dict[str, object]] = [
        *build_sector_position_timeseries_rows(),
        {
            "security_id": "SEC_A",
            "valuation_date": "2026-01-03",
            "dimensions": {"sector": "TECH", "asset_class": "EQUITY"},
            "ending_market_value_portfolio_currency": "70",
        },
        {
            "security_id": "SEC_B",
            "valuation_date": "2026-01-03",
            "dimensions": {"sector": "HEALTH", "asset_class": "EQUITY"},
            "ending_market_value_portfolio_currency": "30",
        },
    ]
    core_client = RecordingHistoricalAttributionCoreClient(rows=core_rows)
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-stateful", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["TOTAL_RISK"],
                        "metrics": ["VOLATILITY"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )

    assert response.status_code == 200
    attribution_set = response.json()["results"]["YTD"]["attribution_sets"][0]
    assert attribution_set["attribution_type"] == "TOTAL_RISK"
    assert attribution_set["metric"] == "VOLATILITY"
    assert attribution_set["contributors"]
    # The default fake declares group-return evidence absent, so this TOTAL_RISK set
    # keeps the weight proxy with the bounded evidence flag and stays proxy-based.
    assert attribution_set["quality_flags"] == ["group_return_evidence:period_missing"]
    assert attribution_set["risk_basis"] == "weight_proxy"
    assert core_client.position_calls == [
        {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "request_payload": {
                "as_of_date": "2026-01-06",
                "window": {
                    "start_date": "2026-01-02",
                    "end_date": "2026-01-06",
                },
                "frequency": "daily",
                "dimensions": ["sector"],
                "consumer_system": "lotus-risk",
                "page": {"page_size": 5000, "page_token": None},
            },
            "tenant_id": "tenant-a",
            "correlation_id": "corr-attr-stateful",
        }
    ]


def test_historical_attribution_stateful_active_risk_uses_performance_benchmark_exposure_context() -> (
    None
):
    performance_client = build_stateful_attribution_returns_client()
    core_client = RecordingHistoricalAttributionCoreClient()
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-active-stateful", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["ACTIVE_RISK"],
                        "metrics": ["TRACKING_ERROR"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateful"
    attribution_set = body["results"]["YTD"]["attribution_sets"][0]
    assert attribution_set["attribution_type"] == "ACTIVE_RISK"
    assert attribution_set["metric"] == "TRACKING_ERROR"
    assert attribution_set["contributors"]
    assert performance_client.calls[0]["request_payload"]["series_selection"] == {
        "include_portfolio": True,
        "include_benchmark": True,
        "include_risk_free": False,
    }
    assert performance_client.benchmark_exposure_context_calls == [
        {
            "request_payload": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-06",
                "window": {"start_date": "2026-01-02", "end_date": "2026-01-06"},
                "frequency": "DAILY",
                "grouping_dimensions": ["SECTOR"],
                "page": {"page_size": 1000, "page_token": None},
            },
            "tenant_id": "tenant-a",
            "correlation_id": "corr-attr-active-stateful",
        }
    ]
    assert not hasattr(core_client, "get_benchmark_market_series")


def test_historical_attribution_stateful_active_risk_asset_class_contract() -> None:
    performance_client = build_stateful_attribution_returns_client()
    performance_client.benchmark_exposure_context_payload = (
        build_benchmark_exposure_context_response(grouping_dimension="ASSET_CLASS")
    )
    core_client = RecordingHistoricalAttributionCoreClient()

    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-active-asset-class", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["ACTIVE_RISK"],
                        "metrics": ["TRACKING_ERROR"],
                        "grouping_dimensions": ["ASSET_CLASS"],
                    },
                },
            },
        )

    assert response.status_code == 200
    attribution_set = response.json()["results"]["YTD"]["attribution_sets"][0]
    assert attribution_set["attribution_type"] == "ACTIVE_RISK"
    assert attribution_set["metric"] == "TRACKING_ERROR"
    assert attribution_set["grouping_dimension"] == "ASSET_CLASS"
    assert attribution_set["total_value"] is not None
    assert attribution_set["reconciled_sum"] == pytest.approx(
        sum(
            contributor["component_contribution"]
            for contributor in attribution_set["contributors"]
            if contributor["component_contribution"] is not None
        ),
        abs=1e-12,
    )
    assert attribution_set["residual"] == pytest.approx(
        attribution_set["total_value"] - attribution_set["reconciled_sum"],
        abs=1e-12,
    )
    assert attribution_set["quality_flags"] == []
    assert attribution_set["contributors"]
    assert core_client.position_calls[0]["request_payload"]["dimensions"] == ["asset_class"]
    exposure_payload = performance_client.benchmark_exposure_context_calls[0]["request_payload"]
    assert exposure_payload["grouping_dimensions"] == ["ASSET_CLASS"]
    assert not hasattr(core_client, "get_benchmark_market_series")


def test_historical_attribution_stateful_active_risk_issuer_uses_benchmark_context() -> None:
    performance_client = build_stateful_attribution_returns_client()
    performance_client.benchmark_exposure_context_payload = (
        build_benchmark_exposure_context_response(grouping_dimension="ISSUER")
    )

    class _IssuerCoreClient(RecordingHistoricalAttributionCoreClient):
        async def get_instrument_enrichment(
            self,
            *,
            security_ids: list[str],
            correlation_id: str | None,
        ) -> dict[str, object]:
            return {
                "records": [
                    {"security_id": "SEC_A", "issuer_id": "ISSUER_A", "issuer_name": "Issuer A"},
                    {"security_id": "SEC_B", "issuer_id": "ISSUER_B", "issuer_name": "Issuer B"},
                ]
            }

    core_client = _IssuerCoreClient()

    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-active-issuer", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["ACTIVE_RISK"],
                        "metrics": ["TRACKING_ERROR"],
                        "grouping_dimensions": ["ISSUER"],
                    },
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["input_mode"] == "stateful"
    assert body["metadata"]["requested_grouping_dimensions"] == ["ISSUER"]
    assert body["metadata"]["stateful_active_risk_gated_grouping_dimensions"] == []
    assert performance_client.benchmark_exposure_context_calls[0]["request_payload"][
        "grouping_dimensions"
    ] == ["ISSUER"]


def test_historical_attribution_stateful_custom_grouping_is_explicitly_gated() -> None:
    performance_client = build_stateful_attribution_returns_client()
    core_client = RecordingHistoricalAttributionCoreClient()

    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-custom"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["TOTAL_RISK"],
                        "metrics": ["VOLATILITY"],
                        "grouping_dimensions": ["CUSTOM"],
                    },
                },
            },
        )

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "INVALID_REQUEST"
    assert body["message"] == "Request validation failed"
    assert any("grouping_dimension=CUSTOM" in detail["msg"] for detail in body["details"])
    assert body["correlation_id"] == "corr-attr-custom"
    assert performance_client.calls == []
    assert core_client.position_calls == []


def test_historical_attribution_stateful_active_risk_rejects_missing_benchmark_returns() -> None:
    performance_client = build_stateful_attribution_returns_client()
    performance_client.response_payload = {
        "series": {
            "portfolio_returns": [
                {"date": "2026-01-02", "return_value": "0.0100"},
                {"date": "2026-01-05", "return_value": "-0.0050"},
            ]
        }
    }
    core_client = RecordingHistoricalAttributionCoreClient()

    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-missing-bmk-return", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["ACTIVE_RISK"],
                        "metrics": ["TRACKING_ERROR"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )

    assert response.status_code == 424
    body = response.json()["error"]
    assert body["code"] == "FAILED_DEPENDENCY"
    assert body["message"] == "Required upstream dependency data is unavailable."
    assert body["correlation_id"] == "corr-attr-missing-bmk-return"
    assert body["details"]["service"] == "lotus-performance"


def test_historical_attribution_stateful_active_risk_rejects_bad_benchmark_context_shape() -> None:
    performance_client = build_stateful_attribution_returns_client()
    performance_client.benchmark_exposure_context_payload = {
        **build_benchmark_exposure_context_response(),
        "rows": "bad",
    }

    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=RecordingHistoricalAttributionCoreClient(),
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-bad-bmk-context", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["ACTIVE_RISK"],
                        "metrics": ["TRACKING_ERROR"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )

    assert response.status_code == 502
    body = response.json()["error"]
    assert body["code"] == "UPSTREAM_INVALID_RESPONSE"
    assert body["message"] == "Upstream dependency returned an invalid response."
    assert body["correlation_id"] == "corr-attr-bad-bmk-context"


def test_historical_attribution_stateful_active_risk_maps_benchmark_context_500_to_upstream_failure() -> (
    None
):
    class _BenchmarkContextFailurePerformanceClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []
            self.benchmark_exposure_context_calls: list[dict[str, object]] = []

        async def get_returns_series(
            self,
            *,
            request_payload: dict[str, object],
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            self.calls.append(
                {
                    "request_payload": request_payload,
                    "tenant_id": authority.tenant_id,
                    "correlation_id": authority.correlation_id,
                }
            )
            return build_stateful_attribution_returns_client().response_payload

        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            authority: DownstreamAuthority,
        ) -> dict[str, object]:
            self.benchmark_exposure_context_calls.append(
                {
                    "request_payload": request_payload,
                    "tenant_id": authority.tenant_id,
                    "correlation_id": authority.correlation_id,
                }
            )
            raise UpstreamServiceError(
                service="lotus-performance",
                operation="/integration/benchmarks/exposure-context",
                status_code=502,
                code="UPSTREAM_FAILURE",
                message=(
                    "lotus-performance /integration/benchmarks/exposure-context failed (500): "
                    "Internal Server Error"
                ),
                details={
                    "service": "lotus-performance",
                    "operation": "/integration/benchmarks/exposure-context",
                    "upstream_status_code": 500,
                },
                retryable=True,
            )

    performance_client = _BenchmarkContextFailurePerformanceClient()
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=RecordingHistoricalAttributionCoreClient(),
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-bmk-context-500", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["ACTIVE_RISK"],
                        "metrics": ["TRACKING_ERROR"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )

    assert response.status_code == 502
    body = response.json()["error"]
    assert body["code"] == "UPSTREAM_FAILURE"
    assert body["correlation_id"] == "corr-attr-bmk-context-500"
    assert body["details"]["service"] == "lotus-performance"
    assert body["details"]["operation"] == "/integration/benchmarks/exposure-context"
    assert body["details"]["upstream_status_code"] == 500
    assert (
        performance_client.benchmark_exposure_context_calls[0]["correlation_id"]
        == "corr-attr-bmk-context-500"
    )


def _empirical_contribution_response() -> dict[str, object]:
    """Evidence matching the shared returns fixture (pp 1.0 / -0.5 / 0.4): TECH chosen,
    HEALTH derived so sum(w*r) reconciles exactly per date at weights .6/.4."""
    dates = ["2026-01-02", "2026-01-05", "2026-01-06"]
    tech = [2.0, -1.0, 1.0]
    health = [-0.5, 0.25, -0.5]

    def series(weight_pct: float, returns_pp: list[float]) -> list[dict[str, object]]:
        return [
            {"date": day, "return_pct": value, "portfolio_weight_pct": weight_pct}
            for day, value in zip(dates, returns_pp, strict=True)
        ]

    def row(sector: str, weight_pct: float, returns_pp: list[float]) -> dict[str, object]:
        return {
            "key": {"sector": sector},
            "contribution": 0.0,
            "is_other": False,
            "group_return": {
                "status": "READY",
                "currency": "USD",
                "return_basis": "SOURCE_POSITION_VALUATION_TWR",
                "weight_basis": "BEGINNING_CAPITAL_RATIO",
                "series": series(weight_pct, returns_pp),
                "reason": None,
            },
        }

    return {
        "results_by_period": {
            "EXPLICIT": {
                "levels": [
                    {
                        "level": 1,
                        "name": "sector",
                        "rows": [row("TECH", 60.0, tech), row("HEALTH", 40.0, health)],
                    }
                ]
            }
        }
    }


def test_historical_attribution_stateful_empirical_group_returns_end_to_end() -> None:
    performance_client = build_stateful_attribution_returns_client()
    performance_client.contribution_response = _empirical_contribution_response()
    core_client = RecordingHistoricalAttributionCoreClient()
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-empirical", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["TOTAL_RISK"],
                        "metrics": ["VOLATILITY"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )
    assert response.status_code == 200
    body = response.json()

    attribution_set = body["results"]["YTD"]["attribution_sets"][0]
    assert attribution_set["risk_basis"] == "empirical_group_returns"
    assert attribution_set["quality_flags"] == []
    contributors = {c["group_key"]: c for c in attribution_set["contributors"]}
    assert set(contributors) == {"SECTOR_TECH", "SECTOR_HEALTH"}
    # Exact per-date reconciliation: components sum exactly to the decomposed total.
    assert attribution_set["reconciled_sum"] == pytest.approx(
        attribution_set["total_value"], abs=1e-12
    )
    # All calculated sets are empirical: the structural limitation stops composing.
    assert body["metadata"]["calculation_supportability"]["state"] == "ready"
    assert body["metadata"]["calculation_supportability"]["reason"] == "calculation_complete"

    # The evidence request went out with the admitted tenant, an EXPLICIT window over
    # the resolved period, one flat hierarchy level, and untruncated emission bounds.
    assert len(performance_client.contribution_calls) == 1
    contribution_call = performance_client.contribution_calls[0]
    assert contribution_call["tenant_id"] == "tenant-a"
    payload = contribution_call["request_payload"]
    assert payload["analyses"] == [{"period": "EXPLICIT", "frequencies": ["daily"]}]
    assert payload["hierarchy"] == ["sector"]
    # The evidence window is the engine-resolved period window (YTD clamped to the
    # first portfolio observation), not the wider returns-series request window.
    assert payload["report_start_date"] == "2026-01-02"
    assert payload["report_end_date"] == "2026-01-06"
    assert payload["emit"]["threshold_weight"] == 0.0
    assert payload["stateful_input"]["metric_basis"] == "NET"
    assert body["metadata"]["upstream_request_fingerprints"].get(
        "lotus-performance:/performance/contribution"
    )


def _unclassified_contribution_response(*, dimension_field: str) -> dict[str, object]:
    dates = ["2026-01-02", "2026-01-05", "2026-01-06"]
    portfolio_returns = [1.0, -0.5, 0.4]

    def row(group: str) -> dict[str, object]:
        return {
            "key": {dimension_field: group},
            "is_other": False,
            "group_return": {
                "status": "READY",
                "currency": "USD",
                "return_basis": "SOURCE_POSITION_VALUATION_TWR",
                "weight_basis": "BEGINNING_CAPITAL_RATIO",
                "series": [
                    {
                        "date": day,
                        "return_pct": value,
                        "portfolio_weight_pct": 50.0,
                    }
                    for day, value in zip(dates, portfolio_returns, strict=True)
                ],
            },
        }

    return {
        "results_by_period": {
            "EXPLICIT": {
                "levels": [
                    {
                        "name": dimension_field,
                        "rows": [
                            row("TECH" if dimension_field == "sector" else "EQUITY"),
                            row("Unclassified"),
                        ],
                    }
                ]
            }
        }
    }


@pytest.mark.parametrize(
    ("grouping_dimension", "dimension_field", "missing_dimensions", "unknown_key"),
    [
        ("SECTOR", "sector", {"asset_class": "EQUITY"}, "SECTOR_UNKNOWN"),
        (
            "SECTOR",
            "sector",
            {"sector": None, "asset_class": "EQUITY"},
            "SECTOR_UNKNOWN",
        ),
        ("ASSET_CLASS", "asset_class", {"sector": "TECH"}, "ASSET_CLASS_UNKNOWN"),
        (
            "ASSET_CLASS",
            "asset_class",
            {"sector": "TECH", "asset_class": None},
            "ASSET_CLASS_UNKNOWN",
        ),
    ],
    ids=["sector_missing", "sector_null", "asset_class_missing", "asset_class_null"],
)
def test_stateful_route_accepts_performance_unclassified_for_core_missing_dimensions(
    grouping_dimension: str,
    dimension_field: str,
    missing_dimensions: dict[str, object],
    unknown_key: str,
) -> None:
    """Exercise the route with Core's missing/null source dimensions and Performance's actual bucket."""
    dates = ["2026-01-02", "2026-01-05", "2026-01-06"]
    classified_dimensions = {"sector": "TECH", "asset_class": "EQUITY"}
    core_rows: list[dict[str, object]] = []
    for index, valuation_date in enumerate(dates):
        core_rows.extend(
            [
                {
                    "security_id": "SEC_CLASSIFIED",
                    "valuation_date": valuation_date,
                    "dimensions": classified_dimensions,
                    "ending_market_value_portfolio_currency": "50",
                },
                {
                    "security_id": "SEC_MISSING",
                    "valuation_date": valuation_date,
                    "dimensions": missing_dimensions,
                    "ending_market_value_portfolio_currency": "50",
                },
            ]
        )

    performance_client = build_stateful_attribution_returns_client()
    performance_client.contribution_response = _unclassified_contribution_response(
        dimension_field=dimension_field
    )
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=RecordingHistoricalAttributionCoreClient(rows=core_rows),
    ):
        response = TestClient(app).post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-unclassified", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["TOTAL_RISK"],
                        "metrics": ["VOLATILITY"],
                        "grouping_dimensions": [grouping_dimension],
                    },
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    attribution_set = body["results"]["YTD"]["attribution_sets"][0]
    assert attribution_set["risk_basis"] == "empirical_group_returns"
    assert attribution_set["quality_flags"] == []
    assert {item["group_key"] for item in attribution_set["contributors"]} == {
        "SECTOR_TECH" if grouping_dimension == "SECTOR" else "ASSET_CLASS_EQUITY",
        unknown_key,
    }
    assert body["metadata"]["calculation_supportability"]["state"] == "ready"
    contribution_request = performance_client.contribution_calls[0]["request_payload"]
    assert contribution_request["hierarchy"] == [dimension_field]
    assert contribution_request["emit"]["include_unclassified"] is True


def test_stateful_attribution_forwards_core_owned_reporting_currency_without_fx() -> None:
    """The routed Risk workflow preserves Performance's BASE_ONLY source contract.

    These controlled Core rows represent a USD reporting book with USD and EUR
    source positions. Risk asks Performance for group evidence in USD but does
    not request `BOTH` or manufacture FX rates; Performance owns the valuation
    conversion. The no-reporting-currency request remains the same-currency
    control in `test_historical_attribution_stateful_total_risk_happy_path`.
    """
    performance_client = build_stateful_attribution_returns_client()
    core_client = RecordingHistoricalAttributionCoreClient(
        rows=[
            {
                "security_id": "SEC_USD",
                "valuation_date": "2026-01-02",
                "position_currency": "USD",
                "dimensions": {"sector": "TECH", "asset_class": "EQUITY"},
                "ending_market_value_portfolio_currency": "60",
                "ending_market_value_reporting_currency": "60",
            },
            {
                "security_id": "SEC_EUR",
                "valuation_date": "2026-01-02",
                "position_currency": "EUR",
                "dimensions": {"sector": "HEALTH", "asset_class": "EQUITY"},
                "ending_market_value_portfolio_currency": "36",
                "ending_market_value_reporting_currency": "40",
            },
            {
                "security_id": "SEC_USD",
                "valuation_date": "2026-01-05",
                "position_currency": "USD",
                "dimensions": {"sector": "TECH", "asset_class": "EQUITY"},
                "ending_market_value_portfolio_currency": "65",
                "ending_market_value_reporting_currency": "65",
            },
            {
                "security_id": "SEC_EUR",
                "valuation_date": "2026-01-05",
                "position_currency": "EUR",
                "dimensions": {"sector": "HEALTH", "asset_class": "EQUITY"},
                "ending_market_value_portfolio_currency": "31.5",
                "ending_market_value_reporting_currency": "35",
            },
        ]
    )
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        response = TestClient(app).post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-usd", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "reporting_currency": "USD",
                    "net_or_gross": "NET",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["TOTAL_RISK"],
                        "metrics": ["VOLATILITY"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )

    assert response.status_code == 200
    contribution_request = performance_client.contribution_calls[0]["request_payload"]
    assert contribution_request["report_ccy"] == "USD"
    assert contribution_request["currency_mode"] == "BASE_ONLY"
    assert "fx" not in contribution_request
    assert contribution_request["stateful_input"]["metric_basis"] == "NET"
    assert core_client.position_calls[0]["request_payload"]["reporting_currency"] == "USD"


def test_stateful_attribution_keeps_missing_core_groups_on_the_proxy_at_the_route() -> None:
    performance_client = build_stateful_attribution_returns_client()
    performance_client.contribution_response = {
        "results_by_period": {"EXPLICIT": {"levels": [{"name": "sector", "rows": []}]}}
    }
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=RecordingHistoricalAttributionCoreClient(),
    ):
        response = TestClient(app).post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-malformed", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["TOTAL_RISK"],
                        "metrics": ["VOLATILITY"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )

    assert response.status_code == 200
    attribution_set = response.json()["results"]["YTD"]["attribution_sets"][0]
    assert attribution_set["risk_basis"] == "weight_proxy"
    assert attribution_set["quality_flags"] == ["group_return_evidence:group_universe_incomplete"]


def test_stateful_attribution_refuses_malformed_contribution_evidence_at_the_route() -> None:
    performance_client = build_stateful_attribution_returns_client()
    performance_client.contribution_response = {"results_by_period": {"EXPLICIT": {"levels": []}}}
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=RecordingHistoricalAttributionCoreClient(),
    ):
        response = TestClient(app).post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-malformed", "X-Tenant-Id": "tenant-a"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["TOTAL_RISK"],
                        "metrics": ["VOLATILITY"],
                        "grouping_dimensions": ["SECTOR"],
                    },
                },
            },
        )

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_INVALID_RESPONSE"
    assert error["details"]["service"] == "lotus-performance"
    assert error["details"]["operation"] == "/performance/contribution"


def test_stateless_conflicting_duplicate_exposure_weights_refuse_400() -> None:
    payload = build_stateless_attribution_payload()
    exposure = payload["stateless_input"]["exposure_history"]  # type: ignore[index]
    first = dict(exposure[0])
    first["weight"] = float(first["weight"]) / 2 + 0.05
    exposure.append(first)
    client = TestClient(app)
    response = client.post("/analytics/risk/historical-attribution", json=payload)
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_INPUT"
    assert "conflicting duplicate exposure weights" in body["message"]
