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
