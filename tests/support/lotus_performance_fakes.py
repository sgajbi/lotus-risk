from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar


class RecordingLotusPerformanceClient:
    def __init__(
        self,
        *,
        response_payload: dict[str, Any],
        benchmark_exposure_context_payload: dict[str, Any] | None = None,
    ) -> None:
        self.response_payload = response_payload
        self.benchmark_exposure_context_payload = benchmark_exposure_context_payload
        self.calls: list[dict[str, Any]] = []
        self.benchmark_exposure_context_calls: list[dict[str, Any]] = []

    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "request_payload": request_payload,
                "correlation_id": correlation_id,
            }
        )
        return self.response_payload

    async def get_benchmark_exposure_context(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        self.benchmark_exposure_context_calls.append(
            {
                "request_payload": request_payload,
                "correlation_id": correlation_id,
            }
        )
        if self.benchmark_exposure_context_payload is None:
            raise AssertionError("benchmark exposure context payload was not configured")
        return self.benchmark_exposure_context_payload

    @property
    def request_payload(self) -> dict[str, Any] | None:
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
    response_factory: Callable[[], dict[str, Any]],
    benchmark_exposure_context_response_factory: Callable[[], dict[str, Any]] | None = None,
) -> type[Any]:
    class _AutoWiredLotusPerformanceClient:
        calls: ClassVar[list[dict[str, Any]]] = []
        benchmark_exposure_context_calls: ClassVar[list[dict[str, Any]]] = []

        async def get_returns_series(
            self,
            *,
            request_payload: dict[str, Any],
            correlation_id: str | None,
        ) -> dict[str, Any]:
            _AutoWiredLotusPerformanceClient.calls.append(
                {
                    "request_payload": request_payload,
                    "correlation_id": correlation_id,
                }
            )
            return response_factory()

        async def get_benchmark_exposure_context(
            self,
            *,
            request_payload: dict[str, Any],
            correlation_id: str | None,
        ) -> dict[str, Any]:
            _AutoWiredLotusPerformanceClient.benchmark_exposure_context_calls.append(
                {
                    "request_payload": request_payload,
                    "correlation_id": correlation_id,
                }
            )
            if benchmark_exposure_context_response_factory is None:
                raise AssertionError(
                    "benchmark exposure context response factory was not configured"
                )
            return benchmark_exposure_context_response_factory()

    return _AutoWiredLotusPerformanceClient
