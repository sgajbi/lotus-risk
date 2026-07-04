from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

from fastapi import Request


class LotusPerformanceClientProtocol(Protocol):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_benchmark_exposure_context(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


class LotusCoreClientProtocol(Protocol):
    async def create_simulation_session(
        self,
        *,
        portfolio_id: str,
        ttl_hours: int | None,
        created_by: str | None,
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, Any]],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_risk_free_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_risk_free_coverage(
        self,
        *,
        currency: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


class RuntimeCompositionError(RuntimeError):
    def __init__(self, *, dependency_name: str, state_attribute: str) -> None:
        super().__init__(f"runtime dependency {dependency_name} is not initialized")
        self.dependency_name = dependency_name
        self.state_attribute = state_attribute


@dataclass(frozen=True)
class RuntimeDownstreamClients:
    app_state: Any

    def lotus_performance(self) -> LotusPerformanceClientProtocol:
        return cast(
            LotusPerformanceClientProtocol,
            _required_client(
                self.app_state,
                dependency_name="lotus-performance",
                state_attribute="lotus_performance_client",
            ),
        )

    def lotus_core(self) -> LotusCoreClientProtocol:
        return cast(
            LotusCoreClientProtocol,
            _required_client(
                self.app_state,
                dependency_name="lotus-core",
                state_attribute="lotus_core_client",
            ),
        )


def _required_client(
    app_state: Any,
    *,
    dependency_name: str,
    state_attribute: str,
) -> Any:
    client = getattr(app_state, state_attribute, None)
    if client is None:
        raise RuntimeCompositionError(
            dependency_name=dependency_name,
            state_attribute=state_attribute,
        )
    return client


def runtime_downstream_clients(request: Request) -> RuntimeDownstreamClients:
    return RuntimeDownstreamClients(app_state=request.app.state)


__all__ = [
    "LotusCoreClientProtocol",
    "LotusPerformanceClientProtocol",
    "RuntimeCompositionError",
    "RuntimeDownstreamClients",
    "runtime_downstream_clients",
]
