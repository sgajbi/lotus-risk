from typing import Any

from fastapi import Request

from app.integrations.lotus_core_client import LotusCoreClient
from app.integrations.lotus_performance_client import LotusPerformanceClient


def resolve_lotus_performance_client(request: Request) -> Any:
    performance_client = getattr(request.app.state, "lotus_performance_client", None)
    if performance_client is not None:
        return performance_client
    return LotusPerformanceClient()


def resolve_lotus_core_client(request: Request) -> Any:
    core_client = getattr(request.app.state, "lotus_core_client", None)
    if core_client is not None:
        return core_client
    return LotusCoreClient()
