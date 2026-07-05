from __future__ import annotations

from typing import Any, cast

import pytest

from app.contracts.concentration import (
    ConcentrationRequest,
    IssuerGroupingLevel,
    IssuerMappingInput,
)
from app.services.concentration.datamodels import IssuerEntry, IssuerIdentity, PositionEntry
from app.services.concentration.parsing import (
    _apply_snapshot_display_names,
    _caller_issuer_map,
    _extract_issuer_map,
    _extract_values_from_snapshot_positions,
    _extract_values_with_issuer_from_snapshot,
    _issuer_key_from_mapping,
    _issuer_key_from_position,
)
from app.services.concentration.math import _coverage_ratio, _uncovered_count
from app.services.concentration_engine import (
    calculate_concentration,
)


class _MalformedEnrichmentCoreClient:
    async def get_instrument_enrichment(
        self, *, security_ids: list[str], correlation_id: str | None
    ) -> dict[str, Any]:
        malformed_records: list[Any] = [
            "invalid-row",
            {"security_id": None, "issuer_id": "X"},
            {"security_id": "A", "issuer_id": "ISSUER_A"},
        ]
        return {"records": malformed_records}

    async def create_simulation_session(
        self,
        *,
        portfolio_id: str,
        ttl_hours: int | None,
        created_by: str | None,
        correlation_id: str | None,
    ) -> dict[str, Any]:
        raise AssertionError("not expected")

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, Any]],
        correlation_id: str | None,
        idempotency_key: str,
        change_set_fingerprint: str,
    ) -> dict[str, Any]:
        raise AssertionError("not expected")

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        raise AssertionError("not expected")


class _MissingRecordsCoreClient(_MalformedEnrichmentCoreClient):
    async def get_instrument_enrichment(
        self, *, security_ids: list[str], correlation_id: str | None
    ) -> dict[str, Any]:
        return {"records": "bad-shape"}


def test_helper_extract_issuer_map_branches() -> None:
    issuer_map, note = _extract_issuer_map(
        {"instrument_enrichment": [{"security_id": "SEC_A", "issuer_id": "ISSUER_A"}]},
        grouping_level=IssuerGroupingLevel.LEGAL_ISSUER,
    )
    assert note is None
    assert issuer_map["SEC_A"] == IssuerIdentity(issuer_id="ISSUER_A", issuer_name=None)

    empty_map, empty_note = _extract_issuer_map(
        {"instrument_enrichment": [{"security_id": "SEC_A"}]},
        grouping_level=IssuerGroupingLevel.LEGAL_ISSUER,
    )
    assert empty_map == {}
    assert empty_note == "issuer_id missing in lotus-core instrument_enrichment"


def test_helper_caller_issuer_map_ultimate_parent_branch() -> None:
    mappings = [
        IssuerMappingInput(
            security_id="SEC_A",
            issuer_id="ISSUER_A",
            ultimate_parent_issuer_id="PARENT_A",
        )
    ]
    issuer_map = _caller_issuer_map(
        mappings=mappings,
        grouping_level=IssuerGroupingLevel.ULTIMATE_PARENT,
    )
    assert issuer_map["SEC_A"] == IssuerIdentity(issuer_id="PARENT_A", issuer_name=None)


def test_helper_issuer_key_resolution_covers_legal_issuer_and_missing_ids() -> None:
    assert _issuer_key_from_mapping(
        IssuerMappingInput(security_id="SEC_A", issuer_id="ISSUER_A", issuer_name="Issuer A"),
        grouping_level=IssuerGroupingLevel.LEGAL_ISSUER,
    ) == IssuerIdentity(issuer_id="ISSUER_A", issuer_name="Issuer A")
    assert (
        _issuer_key_from_mapping(
            IssuerMappingInput(security_id="SEC_A"),
            grouping_level=IssuerGroupingLevel.LEGAL_ISSUER,
        )
        is None
    )
    assert _issuer_key_from_position(
        issuer_id="ISSUER_B",
        issuer_name="Issuer B",
        ultimate_parent_issuer_id=None,
        ultimate_parent_issuer_name=None,
        grouping_level=IssuerGroupingLevel.LEGAL_ISSUER,
    ) == IssuerIdentity(issuer_id="ISSUER_B", issuer_name="Issuer B")
    assert (
        _issuer_key_from_position(
            issuer_id=None,
            issuer_name=None,
            ultimate_parent_issuer_id=None,
            ultimate_parent_issuer_name=None,
            grouping_level=IssuerGroupingLevel.LEGAL_ISSUER,
        )
        is None
    )


def test_extract_snapshot_position_values_handles_empty_and_quantity_fallback() -> None:
    assert _extract_values_from_snapshot_positions(None) == []
    rows: list[Any] = [
        "bad-row",
        {"market_value_base": None, "quantity": "12.5"},
        {"market_value_base": "-1", "quantity": None},
    ]
    assert _extract_values_from_snapshot_positions(cast(list[dict[str, Any]], rows)) == [12.5]


def test_extract_values_with_issuer_handles_fallback_and_non_dict_rows() -> None:
    rows: list[Any] = [
        {"security_id": "SEC_A", "market_value_base": None, "quantity": "10"},
        "bad-row",
        {"security_id": "SEC_B", "market_value_base": None, "quantity": None},
    ]
    values, issuer_values, covered, total = _extract_values_with_issuer_from_snapshot(
        cast(list[dict[str, Any]] | None, rows),
        {"SEC_A": IssuerIdentity(issuer_id="ISSUER_A", issuer_name=None)},
    )
    assert values == [PositionEntry(security_id="SEC_A", security_name=None, value=10.0)]
    assert issuer_values == [IssuerEntry(issuer_id="ISSUER_A", issuer_name=None, value=10.0)]
    assert covered == 1
    assert total == 1


def test_extract_values_with_issuer_aggregates_multiple_positions_for_same_issuer() -> None:
    values, issuer_values, covered, total = _extract_values_with_issuer_from_snapshot(
        [
            {"security_id": "SEC_A", "instrument_name": "Bond A", "market_value_base": "10"},
            {"security_id": "SEC_B", "instrument_name": "Bond B", "market_value_base": "15"},
        ],
        {
            "SEC_A": IssuerIdentity(issuer_id="ISSUER_A", issuer_name="Issuer A"),
            "SEC_B": IssuerIdentity(issuer_id="ISSUER_A", issuer_name="Issuer A"),
        },
    )

    assert values == [
        PositionEntry(security_id="SEC_A", security_name="Bond A", value=10.0),
        PositionEntry(security_id="SEC_B", security_name="Bond B", value=15.0),
    ]
    assert issuer_values == [IssuerEntry(issuer_id="ISSUER_A", issuer_name="Issuer A", value=25.0)]
    assert covered == 2
    assert total == 2


def test_snapshot_display_name_enrichment_ignores_malformed_sections_and_rows() -> None:
    sections: dict[str, Any] = {
        "instrument_enrichment": [
            "bad-row",
            {"security_id": "SEC_A", "instrument_name": "Instrument A"},
        ],
        "positions_baseline": [
            "bad-position",
            {"security_id": "SEC_A"},
            {"security_id": "SEC_B", "instrument_name": "Existing Name"},
        ],
        "positions_projected": "bad-shape",
        "positions_delta": [{"security_id": None}],
    }

    _apply_snapshot_display_names(
        sections,
        {"SEC_A": IssuerIdentity(issuer_id="ISSUER_A", issuer_name=None)},
    )

    assert sections["positions_baseline"][1]["instrument_name"] == "Instrument A"
    assert sections["positions_baseline"][2]["instrument_name"] == "Existing Name"


def test_coverage_ratio_handles_zero_and_rounding() -> None:
    assert _coverage_ratio(0, 0) == 0.0
    assert _coverage_ratio(2, 3) == 0.666667


def test_uncovered_count_never_goes_negative() -> None:
    assert _uncovered_count(2, 3) == 1
    assert _uncovered_count(5, 3) == 0


@pytest.mark.asyncio
async def test_stateless_concentration_handles_malformed_core_enrichment_records() -> None:
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "stateless",
            "stateless_input": {
                "current_positions": [{"security_id": "A", "quantity": 60}],
                "projected_positions": [{"security_id": "A", "proposed_quantity": 60}],
            },
        }
    )
    response = await calculate_concentration(request, core_client=_MalformedEnrichmentCoreClient())
    assert response.issuer_concentration.covered_position_count_current == 1


@pytest.mark.asyncio
async def test_stateless_concentration_sets_note_when_core_records_shape_invalid() -> None:
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "stateless",
            "stateless_input": {
                "current_positions": [{"security_id": "A", "quantity": 60}],
                "projected_positions": [{"security_id": "A", "proposed_quantity": 60}],
            },
        }
    )
    response = await calculate_concentration(request, core_client=_MissingRecordsCoreClient())
    assert (
        response.issuer_concentration.note == "lotus-core enrichment payload missing records list"
    )
    assert response.issuer_concentration.uncovered_position_count_current == 1
    assert response.issuer_concentration.uncovered_position_count_proposed == 1
    assert response.issuer_concentration.coverage_ratio_current == 0.0
    assert response.issuer_concentration.coverage_ratio_proposed == 0.0
