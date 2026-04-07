from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import httpx


def fetch_live_returns_series(
    *,
    base_url: str,
    request_payload: dict[str, Any],
    poll_attempts: int = 30,
    poll_interval_seconds: float = 1.0,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(f"{base_url}/integration/returns/series", json=request_payload)
        response.raise_for_status()
        body = response.json()

        if isinstance(body.get("series"), dict):
            return body

        result_path = body.get("result_path")
        if not isinstance(result_path, str):
            raise AssertionError("live returns-series response missing result_path")

        for _ in range(poll_attempts):
            result_response = client.get(f"{base_url}{result_path}")
            result_response.raise_for_status()
            result_body = result_response.json()
            if isinstance(result_body.get("series"), dict):
                return result_body
            time.sleep(poll_interval_seconds)

    raise AssertionError("timed out waiting for live returns-series result")


def extract_decimal_returns(rows: Sequence[dict[str, Any]]) -> list[tuple[str, float]]:
    result: list[tuple[str, float]] = []
    for row in rows:
        date_value = row.get("date")
        return_value = row.get("return_value")
        if not isinstance(date_value, str):
            continue
        result.append((date_value, float(return_value)))
    return result
