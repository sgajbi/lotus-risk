from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_LOTUS_PERFORMANCE_BASE_URL = "http://performance.dev.lotus"


class LotusPerformanceClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        configured_base_url = base_url or os.getenv("LOTUS_PERFORMANCE_BASE_URL")
        if not configured_base_url:
            configured_base_url = DEFAULT_LOTUS_PERFORMANCE_BASE_URL
        self._base_url = configured_base_url.rstrip("/")
        self._timeout = httpx.Timeout(
            timeout_seconds or float(os.getenv("LOTUS_PERFORMANCE_TIMEOUT_SECONDS", "10"))
        )

    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        path = "/integration/returns/series"
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=request_payload, headers=headers)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("lotus-performance returned invalid JSON payload")
                return payload
        except httpx.HTTPStatusError as exc:
            detail = self._extract_error_detail(exc.response)
            raise ValueError(
                f"lotus-performance {path} failed ({exc.response.status_code}): {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ValueError(f"lotus-performance {path} unavailable: {exc}") from exc

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text or "unknown error"
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail
            if isinstance(detail, dict):
                message = detail.get("message")
                if isinstance(message, str):
                    return message
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str):
                    return message
        return str(payload)
