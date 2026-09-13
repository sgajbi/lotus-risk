from __future__ import annotations

from typing import Any

from app.contracts.attribution import (
    AttributionInputMode,
    HistoricalAttributionResponse,
    HistoricalAttributionStatefulInput,
)
from app.contracts.downstream_authority import DownstreamAuthority
from app.services.attribution_engine import calculate_historical_attribution
from app.services.attribution_stateful_inputs import (
    LotusCoreClientProtocol,
    LotusPerformanceClientProtocol,
    resolve_stateful_attribution_inputs,
)
from app.services.audit_lineage import ordered_source_services, upstream_request_fingerprint


def _attach_stateful_lineage(
    *,
    response: HistoricalAttributionResponse,
    returns_request: dict[str, Any],
) -> HistoricalAttributionResponse:
    response.metadata.source_services = ordered_source_services(
        "lotus-performance",
        "lotus-core",
    )
    response.metadata.upstream_request_fingerprints = upstream_request_fingerprint(
        service="lotus-performance",
        operation="/integration/returns/series",
        payload=returns_request,
    )
    return response


async def calculate_historical_attribution_stateful(
    stateful: HistoricalAttributionStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol,
    authority: DownstreamAuthority,
) -> HistoricalAttributionResponse:
    resolved_inputs = await resolve_stateful_attribution_inputs(
        stateful,
        performance_client=performance_client,
        core_client=core_client,
        authority=authority,
    )
    response = calculate_historical_attribution(
        resolved_inputs.stateless_input,
        input_mode=AttributionInputMode.STATEFUL,
        group_evidence=resolved_inputs.group_evidence,
    )
    return _attach_stateful_lineage(
        response=response,
        returns_request=resolved_inputs.returns_request,
    )
