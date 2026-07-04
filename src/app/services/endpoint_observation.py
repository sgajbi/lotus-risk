from collections.abc import Awaitable, Callable
from typing import TypeVar, cast

from app.services.observability_ports import observation_start, record_endpoint_execution

ResponseT = TypeVar("ResponseT")


async def observed_endpoint(
    *,
    endpoint: str,
    input_mode: str,
    operation: Callable[[], ResponseT | Awaitable[ResponseT]],
) -> ResponseT:
    started_at = observation_start()
    try:
        result = operation()
        if isinstance(result, Awaitable):
            result = await result
    except Exception:
        record_endpoint_execution(
            endpoint=endpoint,
            input_mode=input_mode,
            outcome="failure",
            started_at=started_at,
        )
        raise
    record_endpoint_execution(
        endpoint=endpoint,
        input_mode=input_mode,
        outcome="success",
        started_at=started_at,
    )
    return cast(ResponseT, result)
