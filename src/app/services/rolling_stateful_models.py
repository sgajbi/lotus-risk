from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.risk import ReturnPoint
from app.contracts.rolling import RollingStatefulInput


class LotusPerformanceClientProtocol(Protocol):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


class LotusCoreClientProtocol(Protocol):
    async def get_core_snapshot(
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


@dataclass(frozen=True)
class StatefulSourceResponses:
    source_payload: dict[str, Any]
    source_response: dict[str, Any]
    risk_free_request: dict[str, Any] | None
    risk_free_response: dict[str, Any] | None


@dataclass(frozen=True)
class ResolvedStatefulRollingInputs:
    stateful: RollingStatefulInput
    include_risk_free: bool
    source_payload: dict[str, Any]
    risk_free_request: dict[str, Any] | None
    portfolio_points: list[ReturnPoint]
    benchmark_points: list[ReturnPoint]
    risk_free_points: list[ReturnPoint]


@dataclass(frozen=True)
class ResolvedRiskFreeDependency:
    request: dict[str, Any] | None
    points: list[ReturnPoint]
