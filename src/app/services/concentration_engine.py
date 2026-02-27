from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationMetadata,
    ConcentrationRequest,
    ConcentrationResponse,
    ConcentrationRiskProxy,
    ConcentrationValuationContext,
    SinglePositionConcentration,
    SimulationConcentrationInput,
    StatelessConcentrationInput,
)

SERVICE_NAME = "lotus-risk"
_ROUND_PRECISION = 6


class LotusCoreClientProtocol(Protocol):
    async def create_simulation_session(
        self,
        *,
        portfolio_id: str,
        ttl_hours: int | None,
        created_by: str | None,
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, Any]],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


@dataclass
class ConcentrationComputationInput:
    input_mode: ConcentrationInputMode
    current_values: list[float]
    proposed_values: list[float]
    top_n: int
    valuation_context: ConcentrationValuationContext | None = None
    metadata: ConcentrationMetadata | None = None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if decimal_value <= 0:
        return None
    return decimal_value


def _extract_values_from_snapshot_positions(positions: list[dict[str, Any]] | None) -> list[float]:
    if not positions:
        return []
    values: list[float] = []
    for position in positions:
        if not isinstance(position, dict):
            continue
        candidate = _to_decimal(position.get("market_value_base"))
        if candidate is None:
            candidate = _to_decimal(position.get("quantity"))
        if candidate is not None:
            values.append(float(candidate))
    return values


def _extract_values_from_stateless_payload(payload: StatelessConcentrationInput) -> tuple[list[float], list[float]]:
    current_values: list[float] = []
    for position in payload.current_positions:
        candidate = _to_decimal(position.market_value_base)
        if candidate is None:
            candidate = _to_decimal(position.quantity)
        if candidate is not None:
            current_values.append(float(candidate))

    proposed_values: list[float] = []
    for projected_position in payload.projected_positions:
        candidate = _to_decimal(projected_position.projected_market_value_base)
        if candidate is None:
            candidate = _to_decimal(projected_position.proposed_quantity)
        if candidate is not None:
            proposed_values.append(float(candidate))

    return current_values, proposed_values


def _compute_hhi(values: list[float]) -> float:
    total = sum(abs(v) for v in values)
    if total <= 0:
        return 0.0
    weights = [abs(v) / total for v in values]
    return sum(w * w for w in weights) * 10000.0


def _single_position_metrics(values: list[float], *, top_n: int) -> tuple[float, float]:
    total = sum(abs(v) for v in values)
    if total <= 0:
        return 0.0, 0.0
    weights = sorted((abs(v) / total for v in values), reverse=True)
    top_weight = weights[0]
    top_n_weight = sum(weights[:top_n])
    return top_weight, top_n_weight


def _round(value: float) -> float:
    return round(value, _ROUND_PRECISION)


def _build_response(payload: ConcentrationComputationInput) -> ConcentrationResponse:
    current_hhi = _compute_hhi(payload.current_values)
    proposed_hhi = _compute_hhi(payload.proposed_values) if payload.proposed_values else current_hhi

    current_top, current_top_n = _single_position_metrics(payload.current_values, top_n=payload.top_n)
    if payload.proposed_values:
        proposed_top, proposed_top_n = _single_position_metrics(payload.proposed_values, top_n=payload.top_n)
    else:
        proposed_top, proposed_top_n = current_top, current_top_n

    return ConcentrationResponse(
        source_service=SERVICE_NAME,
        input_mode=payload.input_mode,
        risk_proxy=ConcentrationRiskProxy(
            hhi_current=_round(current_hhi),
            hhi_proposed=_round(proposed_hhi),
            hhi_delta=_round(proposed_hhi - current_hhi),
        ),
        single_position_concentration=SinglePositionConcentration(
            top_position_weight_current=_round(current_top),
            top_position_weight_proposed=_round(proposed_top),
            top_position_weight_delta=_round(proposed_top - current_top),
            top_n_cumulative_weight_current=_round(current_top_n),
            top_n_cumulative_weight_proposed=_round(proposed_top_n),
            top_n_cumulative_weight_delta=_round(proposed_top_n - current_top_n),
            top_n=payload.top_n,
        ),
        valuation_context=payload.valuation_context,
        metadata=payload.metadata,
    )


async def _resolve_stateful(
    request: ConcentrationRequest,
    *,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
) -> ConcentrationComputationInput:
    stateful = request.stateful_input
    assert stateful is not None

    snapshot_payload: dict[str, Any] = {
        "as_of_date": stateful.as_of_date.isoformat(),
        "snapshot_mode": "BASELINE",
        "sections": ["positions_baseline", "portfolio_totals", "instrument_enrichment"],
        "options": {
            "include_zero_quantity_positions": stateful.include_zero_quantity_positions,
            "include_cash_positions": stateful.include_cash_positions,
            "position_basis": "market_value_base",
            "weight_basis": "total_market_value_base",
        },
    }
    if stateful.reporting_currency:
        snapshot_payload["reporting_currency"] = stateful.reporting_currency

    snapshot = await core_client.get_core_snapshot(
        portfolio_id=stateful.portfolio_id,
        request_payload=snapshot_payload,
        correlation_id=correlation_id,
    )
    sections = snapshot.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("lotus-core stateful snapshot missing sections payload")

    baseline_values = _extract_values_from_snapshot_positions(sections.get("positions_baseline"))
    valuation = _extract_valuation_context(snapshot.get("valuation_context"))
    metadata = ConcentrationMetadata(
        as_of_date=stateful.as_of_date,
        portfolio_id=stateful.portfolio_id,
    )
    return ConcentrationComputationInput(
        input_mode=ConcentrationInputMode.STATEFUL,
        current_values=baseline_values,
        proposed_values=baseline_values,
        top_n=stateful.top_n,
        valuation_context=valuation,
        metadata=metadata,
    )


def _extract_valuation_context(raw_context: Any) -> ConcentrationValuationContext | None:
    if not isinstance(raw_context, dict):
        return None
    return ConcentrationValuationContext(
        portfolio_currency=_as_str(raw_context.get("portfolio_currency")),
        reporting_currency=_as_str(raw_context.get("reporting_currency")),
        position_basis=_as_str(raw_context.get("position_basis")),
        weight_basis=_as_str(raw_context.get("weight_basis")),
    )


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _as_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


async def _resolve_simulation(
    request: ConcentrationRequest,
    *,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
    actor_id: str | None,
) -> ConcentrationComputationInput:
    simulation: SimulationConcentrationInput = request.simulation_input  # type: ignore[assignment]
    assert simulation is not None

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
        session_record = session_response.get("session")
        if not isinstance(session_record, dict):
            raise ValueError("lotus-core create simulation session returned invalid response payload")
        resolved_session_id = _as_str(session_record.get("session_id"))
        if not resolved_session_id:
            raise ValueError("lotus-core create simulation session response missing session_id")
        session_id = resolved_session_id
        session_version = _as_int(session_record.get("version"))
        session_expires_at = _as_datetime(session_record.get("expires_at"))

    assert session_id is not None

    if simulation.simulation_changes:
        payload = [change.model_dump(exclude_none=True) for change in simulation.simulation_changes]
        changes_response = await core_client.add_simulation_changes(
            session_id=session_id,
            changes=payload,
            correlation_id=correlation_id,
        )
        session_version = _as_int(changes_response.get("version")) or session_version

    expected_version = simulation.expected_version or session_version

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
            "session_id": session_id,
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

    snapshot = await core_client.get_core_snapshot(
        portfolio_id=simulation.portfolio_id,
        request_payload=snapshot_payload,
        correlation_id=correlation_id,
    )
    sections = snapshot.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("lotus-core simulation snapshot missing sections payload")

    baseline_values = _extract_values_from_snapshot_positions(sections.get("positions_baseline"))
    projected_values = _extract_values_from_snapshot_positions(sections.get("positions_projected"))
    if not projected_values:
        projected_values = baseline_values

    snapshot_simulation = snapshot.get("simulation")
    if isinstance(snapshot_simulation, dict):
        session_version = _as_int(snapshot_simulation.get("version")) or session_version

    valuation = _extract_valuation_context(snapshot.get("valuation_context"))
    metadata = ConcentrationMetadata(
        as_of_date=simulation.as_of_date,
        portfolio_id=simulation.portfolio_id,
        simulation_session_id=session_id,
        simulation_session_version=session_version,
        session_expires_at=session_expires_at,
    )
    return ConcentrationComputationInput(
        input_mode=ConcentrationInputMode.SIMULATION,
        current_values=baseline_values,
        proposed_values=projected_values,
        top_n=simulation.top_n,
        valuation_context=valuation,
        metadata=metadata,
    )


async def calculate_concentration(
    request: ConcentrationRequest,
    *,
    core_client: LotusCoreClientProtocol | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
) -> ConcentrationResponse:
    if request.input_mode == ConcentrationInputMode.STATELESS:
        stateless_input = request.stateless_input
        assert stateless_input is not None
        current_values, proposed_values = _extract_values_from_stateless_payload(stateless_input)
        payload = ConcentrationComputationInput(
            input_mode=ConcentrationInputMode.STATELESS,
            current_values=current_values,
            proposed_values=proposed_values if proposed_values else current_values,
            top_n=stateless_input.top_n,
        )
        return _build_response(payload)

    if core_client is None:
        raise ValueError("lotus-core client is required for stateful and simulation input modes")

    if request.input_mode == ConcentrationInputMode.STATEFUL:
        return _build_response(
            await _resolve_stateful(request, core_client=core_client, correlation_id=correlation_id)
        )

    if request.input_mode == ConcentrationInputMode.SIMULATION:
        return _build_response(
            await _resolve_simulation(
                request,
                core_client=core_client,
                correlation_id=correlation_id,
                actor_id=actor_id,
            )
        )

    raise ValueError(f"Unsupported concentration input_mode: {request.input_mode}")
