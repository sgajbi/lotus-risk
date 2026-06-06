from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, status

from app.integrations.lotus_core_client import LotusCoreClient
from app.integrations.lotus_performance_client import LotusPerformanceClient


@dataclass(frozen=True, slots=True)
class DependencyRuntimeView:
    service: str
    base_url: str
    status: str
    detail: str | None = None
    category: str | None = None
    issue_code: str | None = None


def _resolve_dependency_status_override(
    app: FastAPI,
    service: str,
) -> dict[str, Any] | None:
    overrides = getattr(app.state, "dependency_statuses", None)
    if not isinstance(overrides, dict):
        return None
    value = overrides.get(service)
    return value if isinstance(value, dict) else None


def _dependency_clients(app: FastAPI) -> tuple[LotusCoreClient, LotusPerformanceClient]:
    performance_client = getattr(app.state, "lotus_performance_client", None)
    if performance_client is None:
        performance_client = LotusPerformanceClient()
    core_client = getattr(app.state, "lotus_core_client", None)
    if core_client is None:
        core_client = LotusCoreClient()
    return core_client, performance_client


def _configured_dependency_views(
    *,
    core_client: LotusCoreClient,
    performance_client: LotusPerformanceClient,
) -> list[DependencyRuntimeView]:
    return [
        DependencyRuntimeView(
            service="lotus-core",
            base_url=core_client.base_url,
            status="ok",
            detail="configured",
        ),
        DependencyRuntimeView(
            service="lotus-performance",
            base_url=performance_client.base_url,
            status="ok",
            detail="configured",
        ),
    ]


def _dependency_view_with_override(
    dependency: DependencyRuntimeView,
    override: dict[str, Any] | None,
) -> DependencyRuntimeView:
    if override is None:
        return dependency
    override_status = override.get("status")
    override_detail = override.get("detail")
    override_category = override.get("category")
    override_issue_code = override.get("issue_code")
    return DependencyRuntimeView(
        service=dependency.service,
        base_url=dependency.base_url,
        status=override_status if isinstance(override_status, str) else dependency.status,
        detail=override_detail if isinstance(override_detail, str) else dependency.detail,
        category=override_category if isinstance(override_category, str) else None,
        issue_code=override_issue_code if isinstance(override_issue_code, str) else None,
    )


def resolve_dependency_runtime_views(app: FastAPI) -> list[DependencyRuntimeView]:
    core_client, performance_client = _dependency_clients(app)
    return [
        _dependency_view_with_override(
            dependency,
            _resolve_dependency_status_override(app, dependency.service),
        )
        for dependency in _configured_dependency_views(
            core_client=core_client,
            performance_client=performance_client,
        )
    ]


def resolve_readiness_status(app: FastAPI) -> tuple[int, str, list[DependencyRuntimeView]]:
    dependencies = resolve_dependency_runtime_views(app)
    if bool(getattr(app.state, "is_draining", False)):
        return status.HTTP_503_SERVICE_UNAVAILABLE, "draining", dependencies
    if any(dependency.status == "unavailable" for dependency in dependencies):
        return status.HTTP_503_SERVICE_UNAVAILABLE, "dependency_unavailable", dependencies
    if any(dependency.status == "degraded" for dependency in dependencies):
        return status.HTTP_200_OK, "degraded", dependencies
    return status.HTTP_200_OK, "ready", dependencies


def resolve_ops_status(app: FastAPI) -> tuple[str, list[DependencyRuntimeView]]:
    dependencies = resolve_dependency_runtime_views(app)
    if bool(getattr(app.state, "is_draining", False)):
        return "degraded", dependencies
    if any(dependency.status in {"degraded", "unavailable"} for dependency in dependencies):
        return "degraded", dependencies
    return "ok", dependencies
