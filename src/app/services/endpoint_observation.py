from collections.abc import Awaitable, Callable
from typing import overload

from pydantic import BaseModel

from app.services.observability_ports import observation_start, record_endpoint_execution


def _validate_response_model[ResponseModelT: BaseModel](
    result: object,
    response_model: type[ResponseModelT] | None,
) -> object:
    if response_model is None:
        return result

    validated = (
        result if isinstance(result, response_model) else response_model.model_validate(result)
    )
    validated.model_dump(mode="json")
    return validated


@overload
async def observed_endpoint[ResponseT](
    *,
    endpoint: str,
    input_mode: str,
    operation: Callable[[], ResponseT | Awaitable[ResponseT]],
    response_model: None = None,
) -> ResponseT: ...


@overload
async def observed_endpoint[ResponseModelT: BaseModel](
    *,
    endpoint: str,
    input_mode: str,
    operation: Callable[[], object | Awaitable[object]],
    response_model: type[ResponseModelT],
) -> ResponseModelT: ...


async def observed_endpoint[ResponseModelT: BaseModel](
    *,
    endpoint: str,
    input_mode: str,
    operation: Callable[[], object | Awaitable[object]],
    response_model: type[ResponseModelT] | None = None,
) -> object:
    started_at = observation_start()
    try:
        result: object = operation()
        if isinstance(result, Awaitable):
            result = await result
        result = _validate_response_model(result, response_model)
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
    return result
