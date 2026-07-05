from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.contracts.concentration import SimulationConcentrationInput
from app.service_metadata import SERVICE_NAME
from app.services.audit_lineage import fingerprint_payload
from app.services.concentration.parsing import _as_datetime, _as_int, _as_str
from app.services.concentration.ports import LotusCoreClientProtocol
from app.services.concentration.upstream_contracts import (
    invalid_create_simulation_session_payload,
)

SIMULATION_IDEMPOTENCY_KEY_MAX_LENGTH = 128


@dataclass(frozen=True)
class SimulationSession:
    session_id: str
    version: int | None
    expires_at: datetime | None


async def resolve_simulation_session(
    simulation: SimulationConcentrationInput,
    *,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
    actor_id: str | None,
) -> SimulationSession:
    session_id = simulation.session_id
    session_version: int | None = None
    session_expires_at: datetime | None = None

    should_create_session = simulation.start_new_session or not session_id
    if should_create_session:
        session_response = await core_client.create_simulation_session(
            portfolio_id=simulation.portfolio_id,
            ttl_hours=simulation.session_ttl_hours,
            created_by=actor_id or SERVICE_NAME,
            correlation_id=correlation_id,
        )
        created_session = _created_simulation_session(session_response)
        session_id = created_session.session_id
        session_version = created_session.version
        session_expires_at = created_session.expires_at

    if session_id is None:
        raise ValueError("simulation session_id could not be resolved")
    return SimulationSession(
        session_id=session_id,
        version=session_version,
        expires_at=session_expires_at,
    )


def _created_simulation_session(session_response: dict[str, Any]) -> SimulationSession:
    session_record = session_response.get("session")
    if not isinstance(session_record, dict):
        raise invalid_create_simulation_session_payload(reason="missing_session_record")
    session_id = _as_str(session_record.get("session_id"))
    if not session_id:
        raise invalid_create_simulation_session_payload(reason="missing_session_id")
    return SimulationSession(
        session_id=session_id,
        version=_as_int(session_record.get("version")),
        expires_at=_as_datetime(session_record.get("expires_at")),
    )


async def apply_simulation_changes(
    simulation: SimulationConcentrationInput,
    *,
    session: SimulationSession,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
    idempotency_key: str | None,
) -> SimulationSession:
    if not simulation.simulation_changes:
        return session

    payload = [
        change.model_dump(mode="json", exclude_none=True)
        for change in simulation.simulation_changes
    ]
    normalized_idempotency_key = _validated_idempotency_key(idempotency_key)
    changes_response = await core_client.add_simulation_changes(
        session_id=session.session_id,
        changes=payload,
        correlation_id=correlation_id,
        idempotency_key=normalized_idempotency_key,
        change_set_fingerprint=_change_set_fingerprint(
            session=session,
            simulation=simulation,
            changes=payload,
        ),
    )
    session_version = _as_int(changes_response.get("version")) or session.version
    return SimulationSession(
        session_id=session.session_id,
        version=session_version,
        expires_at=session.expires_at,
    )


def _validated_idempotency_key(idempotency_key: str | None) -> str:
    normalized = idempotency_key.strip() if idempotency_key is not None else ""
    if not normalized:
        raise ValueError(
            "Idempotency-Key header is required when simulation_input.simulation_changes is not empty"
        )
    if len(normalized) > SIMULATION_IDEMPOTENCY_KEY_MAX_LENGTH:
        raise ValueError(
            "Idempotency-Key header must be 128 characters or fewer for concentration simulation"
        )
    return normalized


def _change_set_fingerprint(
    *,
    session: SimulationSession,
    simulation: SimulationConcentrationInput,
    changes: list[dict[str, Any]],
) -> str:
    return fingerprint_payload(
        {
            "portfolio_id": simulation.portfolio_id,
            "session_id": session.session_id,
            "changes": changes,
        }
    )


def simulation_snapshot_payload(
    simulation: SimulationConcentrationInput,
    *,
    session: SimulationSession,
) -> dict[str, Any]:
    expected_version = simulation.expected_version or session.version
    snapshot_payload: dict[str, Any] = {
        "as_of_date": simulation.as_of_date.isoformat(),
        "snapshot_mode": "SIMULATION",
        "sections": [
            "positions_baseline",
            "positions_projected",
            "positions_delta",
            "portfolio_totals",
            "instrument_enrichment",
        ],
        "simulation": {
            "session_id": session.session_id,
        },
        "options": {
            "include_zero_quantity_positions": simulation.include_zero_quantity_positions,
            "include_cash_positions": simulation.include_cash_positions,
            "position_basis": "market_value_base",
            "weight_basis": "total_market_value_base",
        },
    }
    if expected_version is not None:
        snapshot_payload["simulation"]["expected_version"] = expected_version
    if simulation.reporting_currency:
        snapshot_payload["reporting_currency"] = simulation.reporting_currency
    return snapshot_payload


def session_with_snapshot_version(
    session: SimulationSession,
    *,
    snapshot: dict[str, Any],
) -> SimulationSession:
    snapshot_simulation = snapshot.get("simulation")
    if not isinstance(snapshot_simulation, dict):
        return session
    return SimulationSession(
        session_id=session.session_id,
        version=_as_int(snapshot_simulation.get("version")) or session.version,
        expires_at=session.expires_at,
    )
