from __future__ import annotations

from typing import Any

import httpx

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


async def execute_lotus_core_json_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    method: str,
    path: str,
    json_payload: dict[str, Any],
    correlation_id: str | None,
) -> dict[str, Any]:
    headers: dict[str, str] = {}
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id

    url = f"{base_url}{path}"
    started_at = observation_start()
    if client is not None:
        return await _execute_lotus_core_json_request(
            client=client,
            method=method,
            url=url,
            path=path,
            json_payload=json_payload,
            headers=headers,
            started_at=started_at,
        )
    async with profile.make_client() as client:
        return await _execute_lotus_core_json_request(
            client=client,
            method=method,
            url=url,
            path=path,
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
    json_payload: dict[str, Any],
    headers: dict[str, str],
    started_at: float,
) -> dict[str, Any]:
    return await execute_downstream_request_json(
        dependency="lotus-core",
        operation=path,
        started_at=started_at,
        request_factory=lambda: client.request(
            method=method,
            url=url,
            json=json_payload,
            headers=headers,
        ),
        parse_response=lambda response: _parse_json_dict_payload(
            response=response,
            invalid_message=f"lotus-core returned invalid JSON payload for {path}",
        ),
    )


def _parse_json_dict_payload(
    response: httpx.Response,
    *,
    invalid_message: str,
) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise invalid_upstream_payload(
            service="lotus-core",
            operation=response.request.url.path,
            message=invalid_message,
        )
    return payload


__all__ = [
    "DEFAULT_LOTUS_CORE_BASE_URL",
    "execute_lotus_core_json_request",
    "resolve_lotus_core_base_url",
]
