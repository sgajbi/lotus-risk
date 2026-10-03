"""Public Risk journey from admitted tenant through async source qualification."""

import math
import statistics
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.integrations.lotus_performance_client import LotusPerformanceClient
from app.main import app
from tests.support.app_runtime import override_app_runtime
from tests.support.returns_series_payloads import build_returns_series_response


@pytest.mark.asyncio
async def test_returns_coverage_journey_refuses_unqualified_work_and_preserves_partial_figures() -> (
    None
):
    source = build_returns_series_response(
        portfolio_returns=(("2026-01-02", "0.0100"), ("2026-01-05", "-0.0200")),
        as_of_date="2026-01-06",
        requested_points=3,
        missing_points=1,
    )
    calculation_id = source["calculation_id"]
    status_path = f"/performance/executions/{calculation_id}"
    result_path = f"/integration/returns/series/results/{calculation_id}"
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST" and request.url.path == "/integration/returns/series":
            return httpx.Response(
                202,
                json={
                    "calculation_id": calculation_id,
                    "poll_path": status_path,
                    "result_path": result_path,
                },
            )
        if request.method == "GET" and request.url.path == status_path:
            return httpx.Response(200, json={"status": "completed"})
        assert request.method == "GET" and request.url.path == result_path
        return httpx.Response(200, json=source)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as downstream:
        client = LotusPerformanceClient(base_url="http://performance.local", http_client=downstream)
        with override_app_runtime(lotus_performance_client=client), TestClient(app) as api:
            for capability in ("calculate", "drawdown", "rolling-metrics"):
                route = f"/analytics/risk/{capability}"
                stateful: dict[str, Any] = {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "net_or_gross": "NET",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                }
                if capability == "calculate":
                    stateful["metrics"] = ["VOLATILITY"]
                elif capability == "rolling-metrics":
                    stateful["rolling_options"] = {
                        "window_lengths": [2],
                        "metrics": ["ROLLING_VOLATILITY"],
                        "include_time_series": True,
                    }
                payload = {"input_mode": "stateful", "stateful_input": stateful}
                before = len(requests)
                unauthorized = api.post(route, json=payload)
                assert unauthorized.status_code == 401
                assert len(requests) == before
                headers = {"X-Tenant-Id": "tenant-a", "X-Correlation-Id": f"corr-{capability}"}
                for ratio, expected_status in [
                    ("0.66666667", 200),
                    ("0.66666666", 502),
                    ("0.66666667", 200),
                ]:
                    source["diagnostics"]["coverage"]["coverage_ratio"] = ratio
                    response = api.post(route, headers=headers, json=payload)
                    assert response.status_code == expected_status
                    body = response.json()
                    if expected_status == 502:
                        assert body["error"]["code"] == "UPSTREAM_INVALID_RESPONSE"
                        continue
                    evidence = body["metadata"]["source_returns_evidence"]
                    assert evidence["calculation_id"] == calculation_id
                    assert evidence["coverage_ratio"] == 0.66666667
                    assert evidence["missing_points"] == 1
                    assert body["metadata"]["calculation_supportability"]["state"] == "degraded"
                    result = body["results"]["YTD"]
                    if capability == "calculate":
                        assert result["portfolio_observation_count"] == 2
                        expected = statistics.stdev([1.0, -2.0]) * math.sqrt(252)
                        assert result["metrics"]["VOLATILITY"]["value"] == pytest.approx(expected)
                    elif capability == "drawdown":
                        assert result["portfolio_observation_count"] == 2
                        assert result["summary"]["max_drawdown"] == pytest.approx(-0.02)
                    else:
                        assert result["series_count"] == 2
                        values = result["window_results"][0]["metric_series"]
                        assert len(values) == 2
                        expected = statistics.stdev([0.01, -0.02]) * math.sqrt(252)
                        assert values[-1]["metric_values"]["ROLLING_VOLATILITY"] == pytest.approx(
                            expected
                        )
                assert [(request.method, request.url.path) for request in requests[before:]] == [
                    ("POST", "/integration/returns/series"),
                    ("GET", status_path),
                    ("GET", result_path),
                ] * 3
                assert all(
                    request.headers["X-Tenant-Id"] == "tenant-a" for request in requests[before:]
                )
                assert all(
                    request.headers["X-Correlation-Id"] == headers["X-Correlation-Id"]
                    for request in requests[before:]
                )
