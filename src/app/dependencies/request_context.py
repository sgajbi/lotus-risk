from fastapi import Request

from app.contracts.downstream_authority import TENANT_ID_HEADER

CORRELATION_ID_HEADER = "X-Correlation-Id"
ACTOR_ID_HEADER = "X-Actor-Id"


def request_correlation_id(request: Request) -> str | None:
    return request.headers.get(CORRELATION_ID_HEADER)


def request_actor_id(request: Request) -> str | None:
    return request.headers.get(ACTOR_ID_HEADER)


def request_tenant_id(request: Request) -> str | None:
    return request.headers.get(TENANT_ID_HEADER)
