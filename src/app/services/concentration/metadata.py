from __future__ import annotations

from datetime import date, datetime

from app.contracts.concentration import ConcentrationMetadata, ConcentrationRequest
from app.services.audit_lineage import fingerprint_model


def build_metadata(
    *,
    request: ConcentrationRequest,
    as_of_date: date | None = None,
    portfolio_id: str | None = None,
    correlation_id: str | None = None,
    simulation_session_id: str | None = None,
    simulation_session_version: int | None = None,
    session_expires_at: datetime | None = None,
    include_cash_positions: bool | None = None,
    include_zero_quantity_positions: bool | None = None,
) -> ConcentrationMetadata:
    return ConcentrationMetadata(
        request_fingerprint=fingerprint_model(request),
        as_of_date=as_of_date,
        portfolio_id=portfolio_id,
        correlation_id=correlation_id,
        simulation_session_id=simulation_session_id,
        simulation_session_version=simulation_session_version,
        session_expires_at=session_expires_at,
        issuer_grouping_level=request.issuer_grouping_level,
        enrichment_policy=request.enrichment_policy,
        include_cash_positions=include_cash_positions,
        include_zero_quantity_positions=include_zero_quantity_positions,
    )
