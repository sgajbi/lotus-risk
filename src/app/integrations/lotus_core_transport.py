from __future__ import annotations

from typing import Any

import httpx

from app.contracts.downstream_authority import (
    DownstreamAuthority,
    downstream_authority_headers,
)
from app.integrations._downstream_client_profile import (
    DownstreamClientProfile,
    execute_downstream_request_json,
)
from app.integrations.downstream_base_url import resolve_downstream_base_url
from app.observability import observation_start
from app.upstream_errors import invalid_upstream_payload

DEFAULT_LOTUS_CORE_BASE_URL = "http://core-control.dev.lotus"


def resolve_lotus_core_base_url(base_url: str | None) -> str:
    return resolve_downstream_base_url(
        explicit_base_url=base_url,
        env_name="LOTUS_CORE_BASE_URL",
        default_base_url=DEFAULT_LOTUS_CORE_BASE_URL,
    )


async def execute_lotus_core_tenant_scoped_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    method: str,
    path: str,
    operation: str,
    json_payload: dict[str, Any],
    authority: DownstreamAuthority,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute a lotus-core request that reads or mutates tenant-owned portfolio state.

    Snapshot, position-timeseries, and simulation-session requests are portfolio-owned and
    must carry the admitted tenant; use :func:`execute_lotus_core_json_request` only for
    global reference reads that are deliberately tenant-free.
    """
    headers: dict[str, str] = dict(extra_headers or {})
    headers.update(downstream_authority_headers(authority))
    return await _execute_with_optional_owned_client(
        profile=profile,
        client=client,
        base_url=base_url,
        method=method,
        path=path,
        operation=operation,
        json_payload=json_payload,
        headers=headers,
    )


async def execute_lotus_core_json_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    method: str,
    path: str,
    operation: str,
    json_payload: dict[str, Any],
    correlation_id: str | None,
    authority: DownstreamAuthority | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Read global Core reference data with per-request caller admission when required.

    A caller tenant header admits a request through Core enterprise security; it does not
    tenant-scope reference facts or add a tenant field to the business payload. Tenant-owned
    portfolio reads still use :func:`execute_lotus_core_tenant_scoped_request`.
    """
    headers: dict[str, str] = dict(extra_headers or {})
    if authority is not None:
        headers.update(downstream_authority_headers(authority))
    elif correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    return await _execute_with_optional_owned_client(
        profile=profile,
        client=client,
        base_url=base_url,
        method=method,
        path=path,
        operation=operation,
        json_payload=json_payload,
        headers=headers,
    )


async def _execute_with_optional_owned_client(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    method: str,
    path: str,
    operation: str,
    json_payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    url = f"{base_url}{path}"
    started_at = observation_start()
    if client is not None:
        return await _execute_lotus_core_json_request(
            client=client,
            method=method,
            url=url,
            path=path,
            operation=operation,
            json_payload=json_payload,
            headers=headers,
            started_at=started_at,
        )
    async with profile.make_client() as owned_client:
        return await _execute_lotus_core_json_request(
            client=owned_client,
            method=method,
            url=url,
            path=path,
            operation=operation,
            json_payload=json_payload,
            headers=headers,
            started_at=started_at,
        )


async def _execute_lotus_core_json_request(
    *,
    client: httpx.AsyncClient,
    method: str,
    url: str,
    path: str,
    operation: str,
    json_payload: dict[str, Any],
    headers: dict[str, str],
    started_at: float,
) -> dict[str, Any]:
    return await execute_downstream_request_json(
        dependency="lotus-core",
        operation=operation,
        started_at=started_at,
        request_factory=lambda: client.request(
            method=method,
            url=url,
            json=json_payload,
            headers=headers,
        ),
        parse_response=lambda response: _parse_json_dict_payload(
            response=response,
            operation=operation,
            invalid_message=f"lotus-core returned invalid JSON payload for {path}",
        ),
    )


def _parse_json_dict_payload(
    response: httpx.Response,
    *,
    operation: str,
    invalid_message: str,
) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise invalid_upstream_payload(
            service="lotus-core",
            operation=operation,
            message=invalid_message,
        )
    return payload


__all__ = [
    "DEFAULT_LOTUS_CORE_BASE_URL",
    "execute_lotus_core_json_request",
    "execute_lotus_core_tenant_scoped_request",
    "resolve_lotus_core_base_url",
]
