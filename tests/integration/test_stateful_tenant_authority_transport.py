"""Registered-route proof that admitted tenant authority reaches the real transports.

These tests exercise the shipped ``LotusPerformanceClient``/``LotusCoreClient`` over a
real ``httpx.MockTransport`` whose behavior mirrors the enforcing lotus-performance
producer at its main (`8f933a84`): a stateful submit without ``X-Tenant-Id`` is refused
with 401 before any durable job, and async result access is scoped to the submitting
tenant (403 ``result_tenant_authority_mismatch`` on foreign reads). Fakes that bypass
the transports cannot prove this boundary, so they are deliberately not used here.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport

from app.integrations.lotus_core_client import LotusCoreClient
from app.integrations.lotus_performance_client import LotusPerformanceClient
from app.main import app
from tests.support.app_runtime import override_app_runtime

_PRODUCER_BASE_URL = "http://performance.enforcing.test"
_CORE_BASE_URL = "http://core-control.enforcing.test"

_TENANT_A_RETURNS = [
    {"date": "2026-01-02", "return_value": "0.0100"},
    {"date": "2026-01-05", "return_value": "0.0100"},
    {"date": "2026-01-06", "return_value": "0.0100"},
]
_TENANT_B_RETURNS = [
    {"date": "2026-01-02", "return_value": "0.0300"},
    {"date": "2026-01-05", "return_value": "-0.0200"},
    {"date": "2026-01-06", "return_value": "0.0150"},
]
_RETURNS_BY_TENANT = {"tenant-a": _TENANT_A_RETURNS, "tenant-b": _TENANT_B_RETURNS}

_MISSING_TENANT_DETAIL = (
    "Stateful input requires X-Tenant-Id before any durable job is accepted or Core read is made."
)


@dataclass
class EnforcingPerformanceProducer:
    """Faithful double of the enforcing producer's tenant admission and result scoping."""

    async_mode: bool = False
    foreign_result_tenant: str | None = None
    requests: list[dict[str, Any]] = field(default_factory=list)
    _submitted_tenants: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _next_calculation: int = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        tenant_id = request.headers.get("X-Tenant-Id", "").strip()
        with self._lock:
            self.requests.append(
                {
                    "method": request.method,
                    "path": request.url.path,
                    "tenant_id": tenant_id or None,
                    "correlation_id": request.headers.get("X-Correlation-Id"),
                }
            )
        if request.url.path == "/integration/returns/series":
            if not tenant_id:
                return httpx.Response(
                    401,
                    json={
                        "detail": _MISSING_TENANT_DETAIL,
                        "message": _MISSING_TENANT_DETAIL,
                    },
                    request=request,
                )
            if not self.async_mode:
                return httpx.Response(
                    200,
                    json={"series": {"portfolio_returns": _RETURNS_BY_TENANT[tenant_id]}},
                    request=request,
                )
            with self._lock:
                self._next_calculation += 1
                calculation_id = f"calc-{self._next_calculation}"
                self._submitted_tenants[calculation_id] = tenant_id
            return httpx.Response(
                202,
                json={
                    "calculation_id": calculation_id,
                    "result_path": f"/integration/returns/series/results/{calculation_id}",
                },
                request=request,
            )
        if request.url.path.startswith("/integration/returns/series/results/"):
            calculation_id = request.url.path.rsplit("/", 1)[-1]
            submitted_tenant = self._submitted_tenants.get(calculation_id)
            result_tenant = self.foreign_result_tenant or submitted_tenant
            if tenant_id != result_tenant:
                return httpx.Response(
                    403,
                    json={
                        "detail": "authorization_policy_denied",
                        "reason": "result_tenant_authority_mismatch",
                    },
                    request=request,
                )
            return httpx.Response(
                200,
                json={"series": {"portfolio_returns": _RETURNS_BY_TENANT[tenant_id]}},
                request=request,
            )
        raise AssertionError(f"unexpected producer path: {request.url.path}")


def _real_performance_client(
    producer: EnforcingPerformanceProducer,
) -> tuple[LotusPerformanceClient, httpx.AsyncClient]:
    pooled_client = httpx.AsyncClient(transport=httpx.MockTransport(producer.handler))
    return (
        LotusPerformanceClient(base_url=_PRODUCER_BASE_URL, http_client=pooled_client),
        pooled_client,
    )


def _recording_core_client() -> tuple[LotusCoreClient, list[dict[str, Any]]]:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "path": request.url.path,
                "tenant_id": request.headers.get("X-Tenant-Id"),
            }
        )
        raise AssertionError(f"unexpected lotus-core request: {request.url.path}")

    pooled_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LotusCoreClient(base_url=_CORE_BASE_URL, http_client=pooled_client), requests


_STATEFUL_PAYLOADS: dict[str, dict[str, Any]] = {
    "/analytics/risk/calculate": {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-01-06",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY"],
        },
    },
    "/analytics/risk/rolling-metrics": {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-01-06",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "rolling_options": {"window_lengths": [2], "metrics": ["ROLLING_VOLATILITY"]},
        },
    },
    "/analytics/risk/drawdown": {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-01-06",
            "periods": [{"type": "YTD", "name": "YTD"}],
        },
    },
    "/analytics/risk/historical-attribution": {
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
    "/analytics/risk/concentration": {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-02-27",
            "top_n": 5,
        },
    },
}


@pytest.mark.parametrize("route", sorted(_STATEFUL_PAYLOADS))
def test_stateful_without_tenant_refuses_before_any_upstream_request(route: str) -> None:
    producer = EnforcingPerformanceProducer()
    performance_client, _ = _real_performance_client(producer)
    core_client, core_requests = _recording_core_client()
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        response = TestClient(app).post(route, json=_STATEFUL_PAYLOADS[route])
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "MISSING_TENANT_AUTHORITY"
    assert error["status"] == 401
    assert producer.requests == []
    assert core_requests == []


@pytest.mark.parametrize(
    ("tenant_header", "expected_status", "expected_code"),
    [
        ("   ", 401, "MISSING_TENANT_AUTHORITY"),
        ("t" * 129, 400, "INVALID_TENANT_AUTHORITY"),
    ],
)
def test_blank_and_oversized_tenant_refusals_make_no_upstream_call(
    tenant_header: str,
    expected_status: int,
    expected_code: str,
) -> None:
    producer = EnforcingPerformanceProducer()
    performance_client, _ = _real_performance_client(producer)
    with override_app_runtime(lotus_performance_client=performance_client):
        response = TestClient(app).post(
            "/analytics/risk/calculate",
            headers={"X-Tenant-Id": tenant_header},
            json=_STATEFUL_PAYLOADS["/analytics/risk/calculate"],
        )
    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
    assert producer.requests == []


def test_stateless_requests_keep_working_without_tenant_authority() -> None:
    producer = EnforcingPerformanceProducer()
    performance_client, _ = _real_performance_client(producer)
    with override_app_runtime(lotus_performance_client=performance_client):
        response = TestClient(app).post(
            "/analytics/risk/calculate",
            json={
                "input_mode": "stateless",
                "stateless_input": {
                    "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
                    "portfolio_open_date": "2026-01-01",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "metrics": ["VOLATILITY"],
                    "returns": [
                        {"date": "2026-01-02", "value": 1.0},
                        {"date": "2026-01-05", "value": -0.5},
                        {"date": "2026-01-06", "value": 0.3},
                    ],
                },
            },
        )
    assert response.status_code == 200
    assert producer.requests == []


def test_enforcing_producer_serves_admitted_tenant_from_shipped_transport() -> None:
    """The pre-fix transport failed exactly here: no tenant header, producer 401."""
    producer = EnforcingPerformanceProducer()
    performance_client, _ = _real_performance_client(producer)
    with override_app_runtime(lotus_performance_client=performance_client):
        response = TestClient(app).post(
            "/analytics/risk/calculate",
            headers={"X-Tenant-Id": "tenant-b", "X-Correlation-Id": "corr-live"},
            json=_STATEFUL_PAYLOADS["/analytics/risk/calculate"],
        )
    assert response.status_code == 200
    assert response.json()["results"]["YTD"]["metrics"]["VOLATILITY"]["value"] > 0.0
    assert producer.requests == [
        {
            "method": "POST",
            "path": "/integration/returns/series",
            "tenant_id": "tenant-b",
            "correlation_id": "corr-live",
        }
    ]


@pytest.mark.asyncio
async def test_two_concurrent_tenants_stay_isolated_on_one_shared_pooled_client() -> None:
    producer = EnforcingPerformanceProducer(async_mode=True)
    performance_client, pooled_client = _real_performance_client(producer)
    payload = _STATEFUL_PAYLOADS["/analytics/risk/calculate"]
    with override_app_runtime(lotus_performance_client=performance_client):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://risk.test"
        ) as api:
            response_a, response_b = await asyncio.gather(
                api.post(
                    "/analytics/risk/calculate",
                    headers={"X-Tenant-Id": "tenant-a"},
                    json=payload,
                ),
                api.post(
                    "/analytics/risk/calculate",
                    headers={"X-Tenant-Id": "tenant-b"},
                    json=payload,
                ),
            )
    await pooled_client.aclose()

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    # Constant returns have zero sample deviation: tenant-a's volatility is exactly 0,
    # anchored outside the service, while tenant-b's varied series must not be.
    volatility_a = response_a.json()["results"]["YTD"]["metrics"]["VOLATILITY"]["value"]
    volatility_b = response_b.json()["results"]["YTD"]["metrics"]["VOLATILITY"]["value"]
    assert volatility_a == 0.0
    assert volatility_b > 0.0

    # Every request each tenant caused -- submit and result polls on the one shared
    # pooled client -- carried exactly that tenant; nothing ran tenantless.
    submits = [r for r in producer.requests if r["method"] == "POST"]
    polls = [r for r in producer.requests if r["method"] == "GET"]
    assert sorted(r["tenant_id"] for r in submits) == ["tenant-a", "tenant-b"]
    assert polls, "async mode must have polled the result path"
    assert all(r["tenant_id"] in {"tenant-a", "tenant-b"} for r in polls)
    for calculation_id, tenant in producer._submitted_tenants.items():
        for poll in polls:
            if poll["path"].endswith(calculation_id):
                assert poll["tenant_id"] == tenant


def test_foreign_tenant_result_access_maps_to_bounded_error_not_endless_pending() -> None:
    producer = EnforcingPerformanceProducer(async_mode=True, foreign_result_tenant="tenant-b")
    performance_client, _ = _real_performance_client(producer)
    with override_app_runtime(lotus_performance_client=performance_client):
        response = TestClient(app).post(
            "/analytics/risk/calculate",
            headers={"X-Tenant-Id": "tenant-a"},
            json=_STATEFUL_PAYLOADS["/analytics/risk/calculate"],
        )
    # The producer's 403 result refusal is a bounded dependency failure, not a
    # pending state: the caller learns the request failed instead of timing out.
    assert response.status_code == 424
    error = response.json()["error"]
    assert error["code"] == "FAILED_DEPENDENCY"
    assert error["details"]["upstream_status_code"] == 403
    assert "result_tenant_authority_mismatch" not in error["message"]
