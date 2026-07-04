from __future__ import annotations

from dataclasses import dataclass

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationMetadata,
    ConcentrationValuationContext,
)


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


@dataclass(frozen=True)
class TopPositionDriverValue:
    security_id: str | None
    security_name: str | None
    weight: float


@dataclass(frozen=True)
class TopIssuerDriverValue:
    issuer_id: str | None
    issuer_name: str | None
    weight: float


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
