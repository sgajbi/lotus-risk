from __future__ import annotations

from typing import Any, Protocol

from app.contracts.downstream_authority import DownstreamAuthority


class LotusCoreClientProtocol(Protocol):
    async def create_simulation_session(
        self,
        *,
        portfolio_id: str,
        ttl_hours: int | None,
        created_by: str | None,
        authority: DownstreamAuthority,
    ) -> dict[str, Any]: ...

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, Any]],
        authority: DownstreamAuthority,
        idempotency_key: str,
        change_set_fingerprint: str,
    ) -> dict[str, Any]: ...

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        authority: DownstreamAuthority,
    ) -> dict[str, Any]: ...

    # Instrument enrichment is a global reference read and stays tenant-free.
    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...
