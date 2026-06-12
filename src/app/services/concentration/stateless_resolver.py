from __future__ import annotations

from dataclasses import dataclass

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationRequest,
    StatelessConcentrationInput,
)
from app.services.concentration.datamodels import (
    ConcentrationComputationInput,
    IssuerEntry,
    IssuerIdentity,
    PositionEntry,
)
from app.services.concentration.metadata import build_metadata
from app.services.concentration.parsing import (
    _extract_values_from_stateless_payload,
    _to_weighted_values,
)
from app.services.concentration.ports import LotusCoreClientProtocol
from app.services.concentration.stateless_issuer_mapping import stateless_issuer_map


@dataclass(frozen=True)
class _WeightedConcentrationState:
    current_positions: list[PositionEntry]
    proposed_positions: list[PositionEntry]
    current_issuers: list[IssuerEntry]
    proposed_issuers: list[IssuerEntry]
    covered_current: int
    covered_proposed: int
    total_current: int
    total_proposed: int
    issuer_note: str | None


def _weighted_stateless_state(
    *,
    current_rows: list[PositionEntry],
    proposed_rows: list[PositionEntry],
    issuer_by_security: dict[str, IssuerIdentity],
    issuer_note: str | None,
) -> _WeightedConcentrationState:
    current_positions, current_issuers, covered_current, total_current = _to_weighted_values(
        current_rows,
        issuer_by_security=issuer_by_security,
    )
    proposed_positions, proposed_issuers, covered_proposed, total_proposed = _to_weighted_values(
        proposed_rows,
        issuer_by_security=issuer_by_security,
    )
    if (
        issuer_note is None
        and (total_current > 0 or total_proposed > 0)
        and (covered_current == 0 and covered_proposed == 0)
    ):
        issuer_note = "issuer mapping unavailable for stateless payload"

    return _WeightedConcentrationState(
        current_positions=current_positions,
        proposed_positions=proposed_positions if proposed_positions else current_positions,
        current_issuers=current_issuers,
        proposed_issuers=proposed_issuers if proposed_issuers else current_issuers,
        covered_current=covered_current,
        covered_proposed=covered_proposed if proposed_positions else covered_current,
        total_current=total_current,
        total_proposed=total_proposed if proposed_positions else total_current,
        issuer_note=issuer_note,
    )


def _stateless_computation_input(
    *,
    request: ConcentrationRequest,
    stateless_input: StatelessConcentrationInput,
    weighted_state: _WeightedConcentrationState,
) -> ConcentrationComputationInput:
    return ConcentrationComputationInput(
        input_mode=ConcentrationInputMode.STATELESS,
        current_positions=weighted_state.current_positions,
        proposed_positions=weighted_state.proposed_positions,
        top_n=stateless_input.top_n,
        current_issuers=weighted_state.current_issuers,
        proposed_issuers=weighted_state.proposed_issuers,
        covered_position_count_current=weighted_state.covered_current,
        covered_position_count_proposed=weighted_state.covered_proposed,
        total_position_count_current=weighted_state.total_current,
        total_position_count_proposed=weighted_state.total_proposed,
        issuer_note=weighted_state.issuer_note,
        metadata=build_metadata(
            request=request,
            include_cash_positions=None,
            include_zero_quantity_positions=None,
        ),
    )


async def resolve_stateless(
    request: ConcentrationRequest,
    *,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> ConcentrationComputationInput:
    stateless_input = request.stateless_input
    if stateless_input is None:
        raise ValueError("stateless_input is required when input_mode=stateless")

    current_rows, proposed_rows = _extract_values_from_stateless_payload(stateless_input)
    all_rows = [*current_rows, *proposed_rows]
    issuer_by_security, issuer_note = await stateless_issuer_map(
        request,
        rows=all_rows,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    weighted_state = _weighted_stateless_state(
        current_rows=current_rows,
        proposed_rows=proposed_rows,
        issuer_by_security=issuer_by_security,
        issuer_note=issuer_note,
    )
    return _stateless_computation_input(
        request=request,
        stateless_input=stateless_input,
        weighted_state=weighted_state,
    )
