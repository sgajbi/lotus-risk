from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any, Self, cast

import httpx
import pytest
from prometheus_client import generate_latest

from app.contracts.downstream_authority import DownstreamAuthority, TenantAuthorityError
from app.integrations.lotus_core_client import (
    DEFAULT_LOTUS_CORE_BASE_URL,
    LotusCoreClient,
)
from app.integrations.lotus_core_operations import build_simulation_session_payload
from app.integrations.lotus_core_transport import resolve_lotus_core_base_url
from app.upstream_errors import UpstreamServiceError
from tests.support.downstream_authority import admitted_test_authority


class _FakeAsyncClient:
    response_factory: Callable[..., httpx.Response] | None = None
    last_request: dict[str, Any] | None = None

    def __init__(self, *, timeout: httpx.Timeout) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def request(
        self,
        *,
        method: str,
        url: str,
        json: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        _FakeAsyncClient.last_request = {
            "method": method,
            "url": url,
            "json": json,
            "headers": headers,
        }
        assert _FakeAsyncClient.response_factory is not None
        return _FakeAsyncClient.response_factory(method=method, url=url, json=json, headers=headers)


def _ok_response(
    payload: Any, *, status_code: int = 200, url: str = "http://localhost/mock"
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("POST", url),
    )


def test_build_simulation_session_payload_omits_empty_optional_fields() -> None:
    payload = build_simulation_session_payload(
        portfolio_id="DEMO_DPM_EUR_001",
        ttl_hours=None,
        created_by="",
    )

    assert payload == {"portfolio_id": "DEMO_DPM_EUR_001"}


@pytest.mark.asyncio
async def test_client_builds_headers_and_payload_for_session_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(
        {"session": {"session_id": "SIM_1"}}
    )

    client = LotusCoreClient(base_url="http://core.local", timeout_seconds=5)
    response = await client.create_simulation_session(
        portfolio_id="DEMO_DPM_EUR_001",
        ttl_hours=24,
        created_by="risk-agent",
        authority=admitted_test_authority("corr-123"),
    )

    assert response["session"]["session_id"] == "SIM_1"
    assert _FakeAsyncClient.last_request is not None
    assert _FakeAsyncClient.last_request["url"] == "http://core.local/simulation-sessions"
    assert _FakeAsyncClient.last_request["json"]["ttl_hours"] == 24
    assert _FakeAsyncClient.last_request["json"]["created_by"] == "risk-agent"
    assert _FakeAsyncClient.last_request["headers"]["X-Correlation-Id"] == "corr-123"
    assert _FakeAsyncClient.last_request["headers"]["X-Tenant-Id"] == "tenant-a"
    metrics = generate_latest().decode("utf-8")
    assert 'lotus_risk_upstream_requests_total{category="ok"' in metrics
    assert 'dependency="lotus-core"' in metrics
    assert 'operation="/simulation-sessions"' in metrics
    assert "DEMO_DPM_EUR_001" not in metrics


@pytest.mark.asyncio
async def test_client_reuses_injected_http_client_without_creating_temporary_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    injected_client = _FakeAsyncClient(timeout=httpx.Timeout(5.0))
    _FakeAsyncClient.response_factory = lambda **_: _ok_response({"ok": True})
    monkeypatch.setattr(
        "app.integrations._downstream_client_profile.DownstreamClientProfile.make_client",
        lambda _: (_ for _ in ()).throw(AssertionError("temporary pool created")),
    )

    client = LotusCoreClient(
        base_url="http://core.local",
        http_client=cast(httpx.AsyncClient, injected_client),
    )
    assert await client.get_core_snapshot(
        portfolio_id="DEMO_DPM_EUR_001",
        request_payload={"snapshot_mode": "BASELINE"},
        authority=admitted_test_authority(),
    ) == {"ok": True}


@pytest.mark.asyncio
async def test_core_snapshot_body_and_header_use_the_same_admitted_risk_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response({"ok": True})
    client = LotusCoreClient(base_url="http://core.local")
    requested = {"as_of_date": "2026-04-10", "sections": ["positions_baseline"]}

    await client.get_core_snapshot(
        portfolio_id="PB_SG_GLOBAL_BAL_001",
        request_payload=requested,
        authority=admitted_test_authority(),
    )

    assert _FakeAsyncClient.last_request is not None
    sent = _FakeAsyncClient.last_request
    assert sent["headers"]["X-Tenant-Id"] == "tenant-a"
    assert sent["json"]["tenant_id"] == "tenant-a"
    assert sent["json"]["consumer_system"] == "lotus-risk"
    assert requested == {"as_of_date": "2026-04-10", "sections": ["positions_baseline"]}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conflict",
    [{"tenant_id": "tenant-b"}, {"consumer_system": "lotus-performance"}],
)
async def test_core_snapshot_refuses_internal_authority_drift_before_transport(
    monkeypatch: pytest.MonkeyPatch,
    conflict: dict[str, str],
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.last_request = None
    _FakeAsyncClient.response_factory = lambda **_: _ok_response({"ok": True})
    client = LotusCoreClient(base_url="http://core.local")

    with pytest.raises(ValueError, match="Core"):
        await client.get_core_snapshot(
            portfolio_id="PB_SG_GLOBAL_BAL_001",
            request_payload={"as_of_date": "2026-04-10", **conflict},
            authority=admitted_test_authority(),
        )

    assert _FakeAsyncClient.last_request is None


@pytest.mark.asyncio
async def test_position_timeseries_identifies_the_admitted_risk_consumer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response({"ok": True})
    client = LotusCoreClient(base_url="http://core.local")

    await client.get_position_analytics_timeseries(
        portfolio_id="PB_SG_GLOBAL_BAL_001",
        request_payload={"as_of_date": "2026-04-10", "period": "ytd"},
        authority=admitted_test_authority(),
    )

    assert _FakeAsyncClient.last_request is not None
    sent = _FakeAsyncClient.last_request
    assert sent["headers"]["X-Tenant-Id"] == "tenant-a"
    assert sent["json"]["consumer_system"] == "lotus-risk"
    assert "tenant_id" not in sent["json"]  # Core timeseries has no body tenant field.


@pytest.mark.asyncio
async def test_shared_core_transport_never_mix_tenants_between_snapshot_requests() -> None:
    observed: list[tuple[str, str, str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        tenant = request.headers["X-Tenant-Id"]
        observed.append((tenant, body["tenant_id"], body["consumer_system"]))
        return httpx.Response(200, json={"owner": tenant})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as pooled:
        client = LotusCoreClient(base_url="http://core.local", http_client=pooled)
        response_a, response_b = await asyncio.gather(
            client.get_core_snapshot(
                portfolio_id="PB_SG_GLOBAL_BAL_001",
                request_payload={"as_of_date": "2026-04-10", "sections": ["portfolio_totals"]},
                authority=admitted_test_authority(tenant_id="tenant-a"),
            ),
            client.get_core_snapshot(
                portfolio_id="PB_SG_GLOBAL_BAL_001",
                request_payload={"as_of_date": "2026-04-10", "sections": ["portfolio_totals"]},
                authority=admitted_test_authority(tenant_id="tenant-b"),
            ),
        )

    assert {response_a["owner"], response_b["owner"]} == {"tenant-a", "tenant-b"}
    assert set(observed) == {
        ("tenant-a", "tenant-a", "lotus-risk"),
        ("tenant-b", "tenant-b", "lotus-risk"),
    }


@pytest.mark.asyncio
async def test_global_risk_free_reference_admits_each_caller_without_scoping_source_data() -> None:
    observed: list[tuple[str, str, dict[str, Any]]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        tenant = request.headers.get("X-Tenant-Id")
        if not tenant:
            return httpx.Response(401, json={"error_code": "TENANT_CONTEXT_REQUIRED"})
        observed.append((request.url.path, tenant, json.loads(request.content)))
        return httpx.Response(200, json={"tenant_id": None, "points": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as pooled:
        client = LotusCoreClient(base_url="http://core.local", http_client=pooled)
        series_request = {"currency": "USD", "as_of_date": "2026-04-10"}
        responses = await asyncio.gather(
            client.get_risk_free_series(
                request_payload=series_request,
                authority=admitted_test_authority(tenant_id="tenant-a"),
            ),
            client.get_risk_free_series(
                request_payload=series_request,
                authority=admitted_test_authority(tenant_id="tenant-b"),
            ),
            client.get_risk_free_coverage(
                currency="USD",
                request_payload={"window": {"start_date": "2026-04-01", "end_date": "2026-04-10"}},
                authority=admitted_test_authority(tenant_id="tenant-a"),
            ),
        )

    assert list(responses) == [{"tenant_id": None, "points": []}] * 3
    assert [(path, tenant) for path, tenant, _ in observed] == [
        ("/integration/reference/risk-free-series", "tenant-a"),
        ("/integration/reference/risk-free-series", "tenant-b"),
        ("/integration/reference/risk-free-series/coverage", "tenant-a"),
    ]
    assert observed[0][2] == observed[1][2] == series_request
    assert all("tenant_id" not in body for _, _, body in observed)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["series", "coverage"])
async def test_risk_free_reference_refuses_missing_caller_authority_before_core_io(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.last_request = None
    client = LotusCoreClient(base_url="http://core.local")
    missing = cast(DownstreamAuthority, None)

    with pytest.raises(TenantAuthorityError) as exc_info:
        if operation == "series":
            await client.get_risk_free_series(
                request_payload={"currency": "USD"}, authority=missing
            )
        else:
            await client.get_risk_free_coverage(
                currency="USD", request_payload={"window": {}}, authority=missing
            )

    assert exc_info.value.code == "MISSING_TENANT_AUTHORITY"
    assert _FakeAsyncClient.last_request is None


@pytest.mark.asyncio
async def test_client_supports_add_changes_and_snapshot_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response({"ok": True})
    client = LotusCoreClient(base_url="http://core.local")

    add_response = await client.add_simulation_changes(
        session_id="SIM_1",
        changes=[{"security_id": "SEC_A", "transaction_type": "BUY"}],
        authority=admitted_test_authority(),
        idempotency_key="idem-sim-1",
        change_set_fingerprint="sha256:change-set-1",
    )
    assert _FakeAsyncClient.last_request is not None
    add_changes_request = _FakeAsyncClient.last_request

    snapshot_response = await client.get_core_snapshot(
        portfolio_id="DEMO_DPM_EUR_001",
        request_payload={"snapshot_mode": "BASELINE"},
        authority=admitted_test_authority(),
    )
    enrichment_response = await client.get_instrument_enrichment(
        security_ids=["SEC_A", "SEC_B"],
        correlation_id=None,
    )
    position_timeseries_response = await client.get_position_analytics_timeseries(
        portfolio_id="DEMO_DPM_EUR_001",
        request_payload={"as_of_date": "2026-02-28"},
        authority=admitted_test_authority(),
    )
    risk_free_response = await client.get_risk_free_series(
        request_payload={
            "currency": "USD",
            "as_of_date": "2026-01-04",
            "series_mode": "annualized_rate_series",
            "window": {"start_date": "2026-01-01", "end_date": "2026-01-04"},
            "frequency": "daily",
        },
        authority=admitted_test_authority(),
    )
    risk_free_coverage_response = await client.get_risk_free_coverage(
        currency="USD",
        request_payload={
            "window": {"start_date": "2026-01-01", "end_date": "2026-01-04"},
        },
        authority=admitted_test_authority(),
    )

    assert add_response == {"ok": True}
    assert add_changes_request["headers"]["Idempotency-Key"] == "idem-sim-1"
    assert add_changes_request["headers"]["X-Lotus-Change-Set-Fingerprint"] == "sha256:change-set-1"
    assert add_changes_request["headers"]["X-Tenant-Id"] == "tenant-a"
    assert snapshot_response == {"ok": True}
    assert enrichment_response == {"ok": True}
    assert position_timeseries_response == {"ok": True}
    assert risk_free_response == {"ok": True}
    assert risk_free_coverage_response == {"ok": True}
    assert _FakeAsyncClient.last_request is not None
    assert (
        _FakeAsyncClient.last_request["url"]
        == "http://core.local/integration/reference/risk-free-series/coverage?currency=USD"
    )
    assert _FakeAsyncClient.last_request["headers"]["X-Tenant-Id"] == "tenant-a"


@pytest.mark.asyncio
async def test_client_rejects_non_object_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(["invalid"])
    client = LotusCoreClient(base_url="http://core.local")

    with pytest.raises(UpstreamServiceError, match="invalid JSON payload") as exc_info:
        await client.get_core_snapshot(
            portfolio_id="DEMO_DPM_EUR_001",
            request_payload={"snapshot_mode": "BASELINE"},
            authority=admitted_test_authority(),
        )
    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_client_maps_http_status_error_without_exposing_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(
        {"detail": "bad request"},
        status_code=400,
    )
    client = LotusCoreClient(base_url="http://core.local")

    with pytest.raises(UpstreamServiceError, match="rejected request \\(400\\)") as exc_info:
        await client.get_core_snapshot(
            portfolio_id="DEMO_DPM_EUR_001",
            request_payload={"snapshot_mode": "BASELINE"},
            authority=admitted_test_authority(),
        )
    assert exc_info.value.code == "FAILED_DEPENDENCY"
    assert exc_info.value.status_code == 424
    assert "bad request" not in exc_info.value.message


@pytest.mark.asyncio
async def test_client_maps_http_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenAsyncClient(_FakeAsyncClient):
        async def request(
            self,
            *,
            method: str,
            url: str,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> httpx.Response:
            raise httpx.ConnectError("network down", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "AsyncClient", _BrokenAsyncClient)
    client = LotusCoreClient(base_url="http://core.local")

    with pytest.raises(UpstreamServiceError, match="unavailable") as exc_info:
        await client.get_core_snapshot(
            portfolio_id="DEMO_DPM_EUR_001",
            request_payload={"snapshot_mode": "BASELINE"},
            authority=admitted_test_authority(),
        )
    assert exc_info.value.code == "UPSTREAM_UNAVAILABLE"
    assert exc_info.value.status_code == 503


def test_client_defaults_to_canonical_core_service_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOTUS_CORE_BASE_URL", raising=False)

    client = LotusCoreClient()

    assert DEFAULT_LOTUS_CORE_BASE_URL == "http://core-control.dev.lotus"
    assert client._base_url == DEFAULT_LOTUS_CORE_BASE_URL


def test_resolve_lotus_core_base_url_prefers_explicit_then_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOTUS_CORE_BASE_URL", "http://env-core.local/")

    assert resolve_lotus_core_base_url("http://explicit-core.local/") == (
        "http://explicit-core.local"
    )
    assert resolve_lotus_core_base_url(None) == "http://env-core.local"
