from __future__ import annotations

from dataclasses import dataclass

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationRequest,
    ConcentrationValuationContext,
    StatelessConcentrationInput,
)
from app.contracts.concentration_stateless_inputs import (
    StatelessExposureBasis,
    stateless_exposure_basis,
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
    projection_supplied: bool,
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
        proposed_positions=proposed_positions if projection_supplied else current_positions,
        current_issuers=current_issuers,
        proposed_issuers=proposed_issuers if projection_supplied else current_issuers,
        covered_current=covered_current,
        covered_proposed=covered_proposed if projection_supplied else covered_current,
        total_current=total_current,
        total_proposed=total_proposed if projection_supplied else total_current,
        issuer_note=issuer_note,
    )


def _stateless_computation_input(
    *,
    request: ConcentrationRequest,
    stateless_input: StatelessConcentrationInput,
    weighted_state: _WeightedConcentrationState,
    correlation_id: str | None,
) -> ConcentrationComputationInput:
    exposure_basis = stateless_exposure_basis(stateless_input)
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
        use_current_state_when_proposed_empty=(
            "projected_positions" not in stateless_input.model_fields_set
        ),
        issuer_note=weighted_state.issuer_note,
        valuation_context=_stateless_valuation_context(exposure_basis),
        metadata=build_metadata(
            request=request,
            correlation_id=correlation_id,
            include_cash_positions=None,
            include_zero_quantity_positions=None,
        ),
    )


def _stateless_valuation_context(
    exposure_basis: StatelessExposureBasis | None,
) -> ConcentrationValuationContext | None:
    if exposure_basis == StatelessExposureBasis.MARKET_VALUE_BASE:
        return ConcentrationValuationContext(
            position_basis="market_value_base",
            weight_basis="total_market_value_base",
        )
    if exposure_basis == StatelessExposureBasis.QUANTITY_PROXY:
        return ConcentrationValuationContext(
            position_basis="quantity_proxy",
            weight_basis="total_quantity_proxy",
        )
    return None


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
        projection_supplied="projected_positions" in stateless_input.model_fields_set,
    )
    return _stateless_computation_input(
        request=request,
        stateless_input=stateless_input,
        weighted_state=weighted_state,
        correlation_id=correlation_id,
    )
