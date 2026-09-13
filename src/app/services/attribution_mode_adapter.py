from __future__ import annotations

from typing import Any

from app.contracts.attribution import (
    AttributionInputMode,
    HistoricalAttributionResponse,
    HistoricalAttributionStatefulInput,
)
from app.contracts.downstream_authority import DownstreamAuthority
from app.services.attribution_engine import calculate_historical_attribution
from app.services.attribution_group_evidence_lineage import canonical_group_evidence_payload
from app.services.attribution_stateful_inputs import (
    LotusCoreClientProtocol,
    LotusPerformanceClientProtocol,
    resolve_stateful_attribution_inputs,
)
from app.services.audit_lineage import (
    fingerprint_payload,
    ordered_source_services,
    upstream_request_fingerprint,
)

CONTRIBUTION_REQUEST_SET_OPERATION = "/performance/contribution"


def _attach_stateful_lineage(
    *,
    response: HistoricalAttributionResponse,
    returns_request: dict[str, Any],
    contribution_requests: tuple[dict[str, Any], ...],
    calculation_input: dict[str, Any],
) -> HistoricalAttributionResponse:
    response.metadata.source_services = ordered_source_services(
        "lotus-performance",
        "lotus-core",
    )
    upstream_fingerprints = upstream_request_fingerprint(
        service="lotus-performance",
        operation="/integration/returns/series",
        payload=returns_request,
    )
    if contribution_requests:
        # The route key stays stable and source-safe.  Its request-set payload
        # retains every resolved-period/dimension request without overwriting
        # repeated calls under the one contribution operation name.
        upstream_fingerprints[f"lotus-performance:{CONTRIBUTION_REQUEST_SET_OPERATION}"] = (
            fingerprint_payload(
                {
                    "requests": sorted(
                        contribution_requests,
                        key=fingerprint_payload,
                    )
                }
            )
        )
    response.metadata.upstream_request_fingerprints = upstream_fingerprints
    # Stateful lineage identifies the calculation inputs that reached covariance,
    # including canonical group evidence.  It intentionally excludes downstream
    # authority; authorization is admission context, not a reproducibility input.
    response.metadata.request_fingerprint = fingerprint_payload(calculation_input)
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
        contribution_requests=resolved_inputs.contribution_requests,
        calculation_input={
            "stateless_input": resolved_inputs.stateless_input.model_dump(
                mode="json",
                exclude_none=False,
            ),
            "group_evidence": canonical_group_evidence_payload(
                resolved_inputs.group_evidence,
                attribution_types=resolved_inputs.stateless_input.attribution_options.attribution_types,
                metrics=resolved_inputs.stateless_input.attribution_options.metrics,
            ),
        },
    )
