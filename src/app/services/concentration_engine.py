from __future__ import annotations

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationRequest,
    ConcentrationResponse,
)
from app.contracts.downstream_authority import (
    DownstreamAuthority,
    required_downstream_authority,
)
from app.services.concentration.ports import LotusCoreClientProtocol
from app.services.concentration.resolvers import (
    resolve_simulation,
    resolve_stateful,
)
from app.services.concentration.response_builder import _build_response
from app.services.concentration.stateless_resolver import resolve_stateless


async def calculate_concentration(
    request: ConcentrationRequest,
    *,
    authority: DownstreamAuthority | None,
    core_client: LotusCoreClientProtocol | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
    idempotency_key: str | None = None,
) -> ConcentrationResponse:
    if request.input_mode == ConcentrationInputMode.STATELESS:
        return _build_response(
            await resolve_stateless(
                request,
                core_client=core_client,
                correlation_id=correlation_id,
            )
        )

    if core_client is None:
        raise ValueError("lotus-core client is required for stateful and simulation input modes")

    if request.input_mode == ConcentrationInputMode.STATEFUL:
        return _build_response(
            await resolve_stateful(
                request,
                core_client=core_client,
                authority=required_downstream_authority(authority),
            )
        )

    if request.input_mode == ConcentrationInputMode.SIMULATION:
        return _build_response(
            await resolve_simulation(
                request,
                core_client=core_client,
                authority=required_downstream_authority(authority),
                actor_id=actor_id,
                idempotency_key=idempotency_key,
            )
        )

    raise ValueError(f"Unsupported concentration input_mode: {request.input_mode}")
