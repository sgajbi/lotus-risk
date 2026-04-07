from __future__ import annotations

from typing import Callable


class RecordingLotusPerformanceClient:
    def __init__(self, *, response_payload: dict[str, object]) -> None:
        self.response_payload = response_payload
        self.calls: list[dict[str, object | None]] = []

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
        return self.response_payload

    @property
    def request_payload(self) -> dict[str, object] | None:
        if not self.calls:
            return None
        payload = self.calls[-1]["request_payload"]
        return payload if isinstance(payload, dict) else None

    @property
    def correlation_id(self) -> str | None:
        if not self.calls:
            return None
        correlation_id = self.calls[-1]["correlation_id"]
        return correlation_id if isinstance(correlation_id, str) or correlation_id is None else None


def build_autowired_lotus_performance_client_class(
    *,
    response_factory: Callable[[], dict[str, object]],
) -> type:
    class _AutoWiredLotusPerformanceClient:
        calls: list[dict[str, object | None]] = []

        async def get_returns_series(
            self,
            *,
            request_payload: dict[str, object],
            correlation_id: str | None,
        ) -> dict[str, object]:
            _AutoWiredLotusPerformanceClient.calls.append(
                {
                    "request_payload": request_payload,
                    "correlation_id": correlation_id,
                }
            )
            return response_factory()

    return _AutoWiredLotusPerformanceClient
