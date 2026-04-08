from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationMetadata,
    ConcentrationRequest,
    ConcentrationResponse,
    ConcentrationRiskProxy,
    ConcentrationValuationContext,
    EnrichmentPolicy,
    IssuerGroupingLevel,
    IssuerConcentration,
    IssuerCoverageStatus,
    TopIssuerDriver,
    TopPositionDriver,
    IssuerMappingInput,
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

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


@dataclass
class IssuerIdentity:
    issuer_id: str
    issuer_name: str | None = None


@dataclass
class PositionEntry:
    security_id: str | None
    security_name: str | None
    value: float


@dataclass
class IssuerEntry:
    issuer_id: str | None
    issuer_name: str | None
    value: float


@dataclass
class ConcentrationComputationInput:
    input_mode: ConcentrationInputMode
    current_positions: list[PositionEntry]
    proposed_positions: list[PositionEntry]
    top_n: int
    current_issuers: list[IssuerEntry]
    proposed_issuers: list[IssuerEntry]
    covered_position_count_current: int
    covered_position_count_proposed: int
    total_position_count_current: int
    total_position_count_proposed: int
    issuer_note: str | None = None
    valuation_context: ConcentrationValuationContext | None = None
    metadata: ConcentrationMetadata | None = None


def _build_metadata(
    *,
    request: ConcentrationRequest,
    as_of_date: date | None = None,
    portfolio_id: str | None = None,
    simulation_session_id: str | None = None,
    simulation_session_version: int | None = None,
    session_expires_at: datetime | None = None,
    include_cash_positions: bool | None = None,
    include_zero_quantity_positions: bool | None = None,
) -> ConcentrationMetadata:
    return ConcentrationMetadata(
        as_of_date=as_of_date,
        portfolio_id=portfolio_id,
        simulation_session_id=simulation_session_id,
        simulation_session_version=simulation_session_version,
        session_expires_at=session_expires_at,
        issuer_grouping_level=request.issuer_grouping_level,
        enrichment_policy=request.enrichment_policy,
        include_cash_positions=include_cash_positions,
        include_zero_quantity_positions=include_zero_quantity_positions,
    )


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


def _extract_values_from_stateless_payload(
    payload: StatelessConcentrationInput,
) -> tuple[list[PositionEntry], list[PositionEntry]]:
    current_rows: list[PositionEntry] = []
    for position in payload.current_positions:
        candidate = _to_decimal(position.market_value_base)
        if candidate is None:
            candidate = _to_decimal(position.quantity)
        if candidate is not None:
            current_rows.append(
                PositionEntry(
                    security_id=position.security_id,
                    security_name=position.security_name,
                    value=float(candidate),
                )
            )

    proposed_rows: list[PositionEntry] = []
    for projected_position in payload.projected_positions:
        candidate = _to_decimal(projected_position.projected_market_value_base)
        if candidate is None:
            candidate = _to_decimal(projected_position.proposed_quantity)
        if candidate is not None:
            proposed_rows.append(
                PositionEntry(
                    security_id=projected_position.security_id,
                    security_name=projected_position.security_name,
                    value=float(candidate),
                )
            )

    return current_rows, proposed_rows


def _issuer_key_from_mapping(
    mapping: IssuerMappingInput,
    *,
    grouping_level: IssuerGroupingLevel,
) -> IssuerIdentity | None:
    if grouping_level == IssuerGroupingLevel.ULTIMATE_PARENT:
        issuer_id = mapping.ultimate_parent_issuer_id or mapping.issuer_id
        issuer_name = mapping.ultimate_parent_issuer_name or mapping.issuer_name
    else:
        issuer_id = mapping.issuer_id
        issuer_name = mapping.issuer_name
    if not issuer_id:
        return None
    return IssuerIdentity(issuer_id=issuer_id, issuer_name=issuer_name)


def _issuer_key_from_position(
    *,
    issuer_id: str | None,
    issuer_name: str | None,
    ultimate_parent_issuer_id: str | None,
    ultimate_parent_issuer_name: str | None,
    grouping_level: IssuerGroupingLevel,
) -> IssuerIdentity | None:
    if grouping_level == IssuerGroupingLevel.ULTIMATE_PARENT:
        resolved_id = ultimate_parent_issuer_id or issuer_id
        resolved_name = ultimate_parent_issuer_name or issuer_name
    else:
        resolved_id = issuer_id
        resolved_name = issuer_name
    if not resolved_id:
        return None
    return IssuerIdentity(issuer_id=resolved_id, issuer_name=resolved_name)


def _to_weighted_values(
    rows: list[PositionEntry],
    *,
    issuer_by_security: dict[str, IssuerIdentity],
) -> tuple[list[PositionEntry], list[IssuerEntry], int, int]:
    issuer_totals: dict[str, IssuerEntry] = {}
    covered = 0
    total = 0
    for row in rows:
        total += 1
        if row.security_id and row.security_id in issuer_by_security:
            issuer = issuer_by_security[row.security_id]
            existing = issuer_totals.get(issuer.issuer_id)
            if existing is None:
                issuer_totals[issuer.issuer_id] = IssuerEntry(
                    issuer_id=issuer.issuer_id,
                    issuer_name=issuer.issuer_name,
                    value=row.value,
                )
            else:
                existing.value += row.value
            covered += 1
    return rows, list(issuer_totals.values()), covered, total


def _values(entries: list[PositionEntry] | list[IssuerEntry]) -> list[float]:
    return [entry.value for entry in entries]


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


def _top_position_driver(entries: list[PositionEntry]) -> TopPositionDriver:
    total = sum(abs(entry.value) for entry in entries)
    if total <= 0 or not entries:
        return TopPositionDriver(security_id=None, security_name=None, weight=0.0)
    top_entry = max(entries, key=lambda entry: (abs(entry.value), entry.security_id or ""))
    return TopPositionDriver(
        security_id=top_entry.security_id,
        security_name=top_entry.security_name,
        weight=_round(abs(top_entry.value) / total),
    )


def _top_issuer_driver(entries: list[IssuerEntry]) -> TopIssuerDriver:
    total = sum(abs(entry.value) for entry in entries)
    if total <= 0 or not entries:
        return TopIssuerDriver(issuer_id=None, issuer_name=None, weight=0.0)
    top_entry = max(entries, key=lambda entry: (abs(entry.value), entry.issuer_id or ""))
    return TopIssuerDriver(
        issuer_id=top_entry.issuer_id,
        issuer_name=top_entry.issuer_name,
        weight=_round(abs(top_entry.value) / total),
    )


def _round(value: float) -> float:
    return round(value, _ROUND_PRECISION)


def _coverage_ratio(covered: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return _round(covered / total)


def _uncovered_count(covered: int, total: int) -> int:
    return max(total - covered, 0)


def _build_response(payload: ConcentrationComputationInput) -> ConcentrationResponse:
    current_values = _values(payload.current_positions)
    proposed_values = _values(payload.proposed_positions)
    current_issuer_values = _values(payload.current_issuers)
    proposed_issuer_values = _values(payload.proposed_issuers)

    current_hhi = _compute_hhi(current_values)
    proposed_hhi = _compute_hhi(proposed_values) if proposed_values else current_hhi

    current_top, current_top_n = _single_position_metrics(current_values, top_n=payload.top_n)
    if proposed_values:
        proposed_top, proposed_top_n = _single_position_metrics(
            proposed_values, top_n=payload.top_n
        )
    else:
        proposed_top, proposed_top_n = current_top, current_top_n

    current_issuer_hhi = _compute_hhi(current_issuer_values)
    proposed_issuer_hhi = (
        _compute_hhi(proposed_issuer_values) if proposed_issuer_values else current_issuer_hhi
    )

    current_issuer_top, _ = _single_position_metrics(current_issuer_values, top_n=1)
    if proposed_issuer_values:
        proposed_issuer_top, _ = _single_position_metrics(proposed_issuer_values, top_n=1)
    else:
        proposed_issuer_top = current_issuer_top

    current_top_position = _top_position_driver(payload.current_positions)
    proposed_top_position = (
        _top_position_driver(payload.proposed_positions)
        if payload.proposed_positions
        else current_top_position
    )
    current_top_issuer = _top_issuer_driver(payload.current_issuers)
    proposed_top_issuer = (
        _top_issuer_driver(payload.proposed_issuers)
        if payload.proposed_issuers
        else current_top_issuer
    )

    coverage_status = IssuerCoverageStatus.UNAVAILABLE
    if payload.total_position_count_current > 0 or payload.total_position_count_proposed > 0:
        if (
            payload.covered_position_count_current == payload.total_position_count_current
            and payload.covered_position_count_proposed == payload.total_position_count_proposed
        ):
            coverage_status = IssuerCoverageStatus.COMPLETE
        elif (
            payload.covered_position_count_current > 0
            or payload.covered_position_count_proposed > 0
        ):
            coverage_status = IssuerCoverageStatus.PARTIAL

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
            top_position_current=current_top_position,
            top_position_proposed=proposed_top_position,
        ),
        issuer_concentration=IssuerConcentration(
            hhi_current=_round(current_issuer_hhi),
            hhi_proposed=_round(proposed_issuer_hhi),
            hhi_delta=_round(proposed_issuer_hhi - current_issuer_hhi),
            top_issuer_weight_current=_round(current_issuer_top),
            top_issuer_weight_proposed=_round(proposed_issuer_top),
            top_issuer_weight_delta=_round(proposed_issuer_top - current_issuer_top),
            coverage_status=coverage_status,
            covered_position_count_current=payload.covered_position_count_current,
            covered_position_count_proposed=payload.covered_position_count_proposed,
            total_position_count_current=payload.total_position_count_current,
            total_position_count_proposed=payload.total_position_count_proposed,
            uncovered_position_count_current=_uncovered_count(
                payload.covered_position_count_current,
                payload.total_position_count_current,
            ),
            uncovered_position_count_proposed=_uncovered_count(
                payload.covered_position_count_proposed,
                payload.total_position_count_proposed,
            ),
            coverage_ratio_current=_coverage_ratio(
                payload.covered_position_count_current,
                payload.total_position_count_current,
            ),
            coverage_ratio_proposed=_coverage_ratio(
                payload.covered_position_count_proposed,
                payload.total_position_count_proposed,
            ),
            note=payload.issuer_note,
            top_issuer_current=current_top_issuer,
            top_issuer_proposed=proposed_top_issuer,
        ),
        valuation_context=payload.valuation_context,
        metadata=payload.metadata,
    )


def _extract_issuer_map(
    sections: dict[str, Any],
    *,
    grouping_level: IssuerGroupingLevel,
) -> tuple[dict[str, IssuerIdentity], str | None]:
    enrichment = sections.get("instrument_enrichment")
    if not isinstance(enrichment, list):
        return {}, "instrument_enrichment missing from lotus-core snapshot"
    issuer_by_security: dict[str, IssuerIdentity] = {}
    for row in enrichment:
        if not isinstance(row, dict):
            continue
        security_id = _as_str(row.get("security_id"))
        if grouping_level == IssuerGroupingLevel.ULTIMATE_PARENT:
            issuer_id = _as_str(row.get("ultimate_parent_issuer_id")) or _as_str(
                row.get("issuer_id")
            )
            issuer_name = _as_str(row.get("ultimate_parent_issuer_name")) or _as_str(
                row.get("issuer_name")
            )
        else:
            issuer_id = _as_str(row.get("issuer_id"))
            issuer_name = _as_str(row.get("issuer_name"))
        if security_id and issuer_id:
            issuer_by_security[security_id] = IssuerIdentity(
                issuer_id=issuer_id,
                issuer_name=issuer_name,
            )
    if not issuer_by_security:
        return {}, "issuer_id missing in lotus-core instrument_enrichment"
    return issuer_by_security, None


def _apply_snapshot_display_names(
    sections: dict[str, Any],
    issuer_by_security: dict[str, IssuerIdentity],
) -> None:
    enrichment = sections.get("instrument_enrichment")
    if not isinstance(enrichment, list):
        return
    security_names: dict[str, str] = {}
    for row in enrichment:
        if not isinstance(row, dict):
            continue
        security_id = _as_str(row.get("security_id"))
        instrument_name = _as_str(row.get("instrument_name"))
        if security_id and instrument_name:
            security_names[security_id] = instrument_name
    for section_name in ("positions_baseline", "positions_projected", "positions_delta"):
        positions = sections.get(section_name)
        if not isinstance(positions, list):
            continue
        for row in positions:
            if not isinstance(row, dict):
                continue
            security_id = _as_str(row.get("security_id"))
            if security_id and security_id in security_names and "instrument_name" not in row:
                row["instrument_name"] = security_names[security_id]


def _caller_issuer_map(
    *,
    mappings: list[IssuerMappingInput],
    grouping_level: IssuerGroupingLevel,
) -> dict[str, IssuerIdentity]:
    issuer_by_security: dict[str, IssuerIdentity] = {}
    for mapping in mappings:
        issuer_key = _issuer_key_from_mapping(mapping, grouping_level=grouping_level)
        if issuer_key:
            issuer_by_security[mapping.security_id] = issuer_key
    return issuer_by_security


def _merge_issuer_maps(
    *,
    caller_map: dict[str, IssuerIdentity],
    core_map: dict[str, IssuerIdentity],
    policy: EnrichmentPolicy,
) -> dict[str, IssuerIdentity]:
    if policy == EnrichmentPolicy.USE_CALLER_ONLY:
        return dict(caller_map)
    if policy == EnrichmentPolicy.CORE_ONLY:
        return dict(core_map)
    merged = dict(core_map)
    merged.update(caller_map)
    return merged


def _extract_values_with_issuer_from_snapshot(
    positions: list[dict[str, Any]] | None,
    issuer_by_security: dict[str, IssuerIdentity],
) -> tuple[list[PositionEntry], list[IssuerEntry], int, int]:
    if not positions:
        return [], [], 0, 0
    position_entries: list[PositionEntry] = []
    issuer_totals: dict[str, IssuerEntry] = {}
    covered = 0
    total = 0
    for position in positions:
        if not isinstance(position, dict):
            continue
        security_id = _as_str(position.get("security_id"))
        security_name = _as_str(position.get("instrument_name"))
        candidate = _to_decimal(position.get("market_value_base"))
        if candidate is None:
            candidate = _to_decimal(position.get("quantity"))
        if candidate is None:
            continue
        numeric_value = float(candidate)
        position_entries.append(
            PositionEntry(
                security_id=security_id,
                security_name=security_name,
                value=numeric_value,
            )
        )
        total += 1
        if security_id and security_id in issuer_by_security:
            issuer = issuer_by_security[security_id]
            existing = issuer_totals.get(issuer.issuer_id)
            if existing is None:
                issuer_totals[issuer.issuer_id] = IssuerEntry(
                    issuer_id=issuer.issuer_id,
                    issuer_name=issuer.issuer_name,
                    value=numeric_value,
                )
            else:
                existing.value += numeric_value
            covered += 1
    return position_entries, list(issuer_totals.values()), covered, total


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

    core_issuer_map, issuer_note = _extract_issuer_map(
        sections, grouping_level=request.issuer_grouping_level
    )
    _apply_snapshot_display_names(sections, core_issuer_map)
    caller_map = _caller_issuer_map(
        mappings=stateful.issuer_mappings,
        grouping_level=request.issuer_grouping_level,
    )
    issuer_by_security = _merge_issuer_maps(
        caller_map=caller_map,
        core_map=core_issuer_map,
        policy=request.enrichment_policy,
    )
    baseline_positions, baseline_issuers, covered_baseline, total_baseline = (
        _extract_values_with_issuer_from_snapshot(
            sections.get("positions_baseline"), issuer_by_security
        )
    )
    valuation = _extract_valuation_context(snapshot.get("valuation_context"))
    metadata = _build_metadata(
        request=request,
        as_of_date=stateful.as_of_date,
        portfolio_id=stateful.portfolio_id,
        include_cash_positions=stateful.include_cash_positions,
        include_zero_quantity_positions=stateful.include_zero_quantity_positions,
    )
    return ConcentrationComputationInput(
        input_mode=ConcentrationInputMode.STATEFUL,
        current_positions=baseline_positions,
        proposed_positions=baseline_positions,
        top_n=stateful.top_n,
        current_issuers=baseline_issuers,
        proposed_issuers=baseline_issuers,
        covered_position_count_current=covered_baseline,
        covered_position_count_proposed=covered_baseline,
        total_position_count_current=total_baseline,
        total_position_count_proposed=total_baseline,
        issuer_note=issuer_note,
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
            raise ValueError(
                "lotus-core create simulation session returned invalid response payload"
            )
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

    core_issuer_map, issuer_note = _extract_issuer_map(
        sections, grouping_level=request.issuer_grouping_level
    )
    _apply_snapshot_display_names(sections, core_issuer_map)
    caller_map = _caller_issuer_map(
        mappings=simulation.issuer_mappings,
        grouping_level=request.issuer_grouping_level,
    )
    issuer_by_security = _merge_issuer_maps(
        caller_map=caller_map,
        core_map=core_issuer_map,
        policy=request.enrichment_policy,
    )
    baseline_positions, baseline_issuers, covered_baseline, total_baseline = (
        _extract_values_with_issuer_from_snapshot(
            sections.get("positions_baseline"), issuer_by_security
        )
    )
    projected_positions, projected_issuers, covered_projected, total_projected = (
        _extract_values_with_issuer_from_snapshot(
            sections.get("positions_projected"), issuer_by_security
        )
    )
    if not projected_positions:
        projected_positions = baseline_positions
    if not projected_issuers:
        projected_issuers = baseline_issuers
        covered_projected = covered_baseline
        total_projected = total_baseline

    snapshot_simulation = snapshot.get("simulation")
    if isinstance(snapshot_simulation, dict):
        session_version = _as_int(snapshot_simulation.get("version")) or session_version

    valuation = _extract_valuation_context(snapshot.get("valuation_context"))
    metadata = _build_metadata(
        request=request,
        as_of_date=simulation.as_of_date,
        portfolio_id=simulation.portfolio_id,
        simulation_session_id=session_id,
        simulation_session_version=session_version,
        session_expires_at=session_expires_at,
        include_cash_positions=simulation.include_cash_positions,
        include_zero_quantity_positions=simulation.include_zero_quantity_positions,
    )
    return ConcentrationComputationInput(
        input_mode=ConcentrationInputMode.SIMULATION,
        current_positions=baseline_positions,
        proposed_positions=projected_positions,
        top_n=simulation.top_n,
        current_issuers=baseline_issuers,
        proposed_issuers=projected_issuers,
        covered_position_count_current=covered_baseline,
        covered_position_count_proposed=covered_projected,
        total_position_count_current=total_baseline,
        total_position_count_proposed=total_projected,
        issuer_note=issuer_note,
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
        current_rows, proposed_rows = _extract_values_from_stateless_payload(stateless_input)

        caller_issuer_map: dict[str, IssuerIdentity] = {}
        for position in stateless_input.current_positions:
            issuer_key = _issuer_key_from_position(
                issuer_id=position.issuer_id,
                issuer_name=None,
                ultimate_parent_issuer_id=position.ultimate_parent_issuer_id,
                ultimate_parent_issuer_name=None,
                grouping_level=request.issuer_grouping_level,
            )
            if issuer_key:
                caller_issuer_map[position.security_id] = issuer_key
        for projected_position in stateless_input.projected_positions:
            issuer_key = _issuer_key_from_position(
                issuer_id=projected_position.issuer_id,
                issuer_name=None,
                ultimate_parent_issuer_id=projected_position.ultimate_parent_issuer_id,
                ultimate_parent_issuer_name=None,
                grouping_level=request.issuer_grouping_level,
            )
            if issuer_key:
                caller_issuer_map[projected_position.security_id] = issuer_key

        core_issuer_map: dict[str, IssuerIdentity] = {}
        issuer_note: str | None = None
        if (
            request.enrichment_policy != EnrichmentPolicy.USE_CALLER_ONLY
            and core_client is not None
        ):
            security_ids = sorted(
                {
                    row.security_id
                    for row in [*current_rows, *proposed_rows]
                    if row.security_id is not None
                }
            )
            if security_ids:
                try:
                    enrichment_payload = await core_client.get_instrument_enrichment(
                        security_ids=security_ids,
                        correlation_id=correlation_id,
                    )
                    records = enrichment_payload.get("records")
                    if isinstance(records, list):
                        for record in records:
                            if not isinstance(record, dict):
                                continue
                            security_id = _as_str(record.get("security_id"))
                            if not security_id:
                                continue
                            if request.issuer_grouping_level == IssuerGroupingLevel.ULTIMATE_PARENT:
                                issuer_id = _as_str(
                                    record.get("ultimate_parent_issuer_id")
                                ) or _as_str(record.get("issuer_id"))
                                issuer_name = _as_str(
                                    record.get("ultimate_parent_issuer_name")
                                ) or _as_str(record.get("issuer_name"))
                            else:
                                issuer_id = _as_str(record.get("issuer_id"))
                                issuer_name = _as_str(record.get("issuer_name"))
                            if issuer_id:
                                core_issuer_map[security_id] = IssuerIdentity(
                                    issuer_id=issuer_id,
                                    issuer_name=issuer_name,
                                )
                    else:
                        issuer_note = "lotus-core enrichment payload missing records list"
                except ValueError:
                    issuer_note = "lotus-core enrichment unavailable for stateless issuer mapping"

        issuer_by_security = _merge_issuer_maps(
            caller_map=caller_issuer_map,
            core_map=core_issuer_map,
            policy=request.enrichment_policy,
        )

        current_positions, current_issuers, covered_current, total_current = _to_weighted_values(
            current_rows,
            issuer_by_security=issuer_by_security,
        )
        proposed_positions, proposed_issuers, covered_proposed, total_proposed = (
            _to_weighted_values(
                proposed_rows,
                issuer_by_security=issuer_by_security,
            )
        )
        if (
            issuer_note is None
            and (total_current > 0 or total_proposed > 0)
            and (covered_current == 0 and covered_proposed == 0)
        ):
            issuer_note = "issuer mapping unavailable for stateless payload"
        payload = ConcentrationComputationInput(
            input_mode=ConcentrationInputMode.STATELESS,
            current_positions=current_positions,
            proposed_positions=proposed_positions if proposed_positions else current_positions,
            top_n=stateless_input.top_n,
            current_issuers=current_issuers,
            proposed_issuers=(proposed_issuers if proposed_issuers else current_issuers),
            covered_position_count_current=covered_current,
            covered_position_count_proposed=(
                covered_proposed if proposed_positions else covered_current
            ),
            total_position_count_current=total_current,
            total_position_count_proposed=(total_proposed if proposed_positions else total_current),
            issuer_note=issuer_note,
            metadata=_build_metadata(
                request=request,
                include_cash_positions=None,
                include_zero_quantity_positions=None,
            ),
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
