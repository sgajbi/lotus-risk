import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.upstream_errors import UpstreamServiceError
from tests.support.app_runtime import override_app_runtime
from tests.support.historical_attribution_fakes import (
    RecordingHistoricalAttributionCoreClient,
    build_benchmark_exposure_context_response,
    build_sector_position_timeseries_rows,
    build_stateful_attribution_returns_client,
)


def _stateless_attribution_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-05", "value": -0.4},
                {"date": "2026-01-06", "value": 0.3},
                {"date": "2026-01-05", "value": 0.6},
                {"date": "2026-01-06", "value": -0.2},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-05", "value": -0.3},
                {"date": "2026-01-06", "value": 0.2},
                {"date": "2026-01-05", "value": 0.4},
                {"date": "2026-01-06", "value": -0.1},
            ],
            "exposure_history": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.55,
                },
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.45,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.52,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.48,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.54,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.46,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.53,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.47,
                },
            ],
            "benchmark_exposure_history": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.48,
                },
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.52,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.47,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.53,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.49,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.51,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.49,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.51,
                },
            ],
            "attribution_options": {
                "attribution_types": ["TOTAL_RISK", "ACTIVE_RISK"],
                "metrics": ["VOLATILITY", "TRACKING_ERROR"],
                "grouping_dimensions": ["SECTOR"],
                "annualization_basis": 252,
            },
        },
    }


def test_historical_attribution_stateless_happy_path() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/historical-attribution",
        json=_stateless_attribution_payload(),
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
    ]
    assert body["metadata"]["stateful_active_risk_gated_grouping_dimensions"] == ["ISSUER"]
    assert (
        body["metadata"]["stateful_active_risk_gate_reason"]
        == "benchmark issuer exposure semantics unavailable"
    )
    assert body["metadata"]["calculation_supportability"] == {
        "state": "ready",
        "reason": "calculation_complete",
        "freshness_bucket": "current",
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
    payload = _stateless_attribution_payload()
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
            headers={"X-Correlation-Id": "corr-attr-stateful"},
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
            headers={"X-Correlation-Id": "corr-attr-stateful"},
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
    assert attribution_set["quality_flags"] == []
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
            headers={"X-Correlation-Id": "corr-attr-active-stateful"},
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
            headers={"X-Correlation-Id": "corr-attr-active-asset-class"},
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


def test_historical_attribution_stateful_active_risk_issuer_is_explicitly_gated() -> None:
    performance_client = build_stateful_attribution_returns_client()
    core_client = RecordingHistoricalAttributionCoreClient()

    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/historical-attribution",
            headers={"X-Correlation-Id": "corr-attr-active-issuer"},
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

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "INVALID_REQUEST"
    assert body["message"] == "Request validation failed"
    assert any("grouping_dimension=ISSUER" in detail["msg"] for detail in body["details"])
    assert body["correlation_id"] == "corr-attr-active-issuer"


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
            headers={"X-Correlation-Id": "corr-attr-missing-bmk-return"},
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
    assert "no benchmark returns" in body["message"]
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
            headers={"X-Correlation-Id": "corr-attr-bad-bmk-context"},
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
    assert "benchmark exposure context payload missing" in body["message"]
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
            correlation_id: str | None,
        ) -> dict[str, object]:
            self.calls.append(
                {
                    "request_payload": request_payload,
                    "correlation_id": correlation_id,
                }
            )
            return build_stateful_attribution_returns_client().response_payload

        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            self.benchmark_exposure_context_calls.append(
                {
                    "request_payload": request_payload,
                    "correlation_id": correlation_id,
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
            headers={"X-Correlation-Id": "corr-attr-bmk-context-500"},
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
