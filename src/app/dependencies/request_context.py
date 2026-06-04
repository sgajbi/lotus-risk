from fastapi import Request

CORRELATION_ID_HEADER = "X-Correlation-Id"
ACTOR_ID_HEADER = "X-Actor-Id"


def request_correlation_id(request: Request) -> str | None:
    return request.headers.get(CORRELATION_ID_HEADER)


def request_actor_id(request: Request) -> str | None:
    return request.headers.get(ACTOR_ID_HEADER)
