from __future__ import annotations

from typing import Any

import pytest

from app.contracts.concentration import ConcentrationRequest
from app.services.concentration_engine import calculate_concentration


class _CoreEnrichmentRecorder:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records
        self.calls: list[dict[str, object]] = []

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "security_ids": security_ids,
                "correlation_id": correlation_id,
            }
        )
        return {"records": self.records}

    async def create_simulation_session(
        self,
        *,
        portfolio_id: str,
        ttl_hours: int | None,
        created_by: str | None,
        correlation_id: str | None,
    ) -> dict[str, Any]:
        raise AssertionError("not expected in stateless characterization tests")

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, Any]],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        raise AssertionError("not expected in stateless characterization tests")

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        raise AssertionError("not expected in stateless characterization tests")


def _stateless_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "current_positions": [
                {"security_id": "A", "quantity": 60, "issuer_id": "CALLER_SHARED"},
                {"security_id": "B", "quantity": 40},
            ],
            "projected_positions": [
                {"security_id": "A", "proposed_quantity": 60, "issuer_id": "CALLER_SHARED"},
                {"security_id": "B", "proposed_quantity": 40},
            ],
        },
    }


@pytest.mark.asyncio
async def test_engine_characterization_merge_policy_prefers_caller_mapping() -> None:
    request = ConcentrationRequest.model_validate(_stateless_payload())
    core_client = _CoreEnrichmentRecorder(
        records=[
            {"security_id": "A", "issuer_id": "CORE_A"},
            {"security_id": "B", "issuer_id": "CALLER_SHARED"},
        ]
    )

    response = await calculate_concentration(request, core_client=core_client, correlation_id="corr-1")

    assert response.issuer_concentration.hhi_current == 10000.0
    assert response.issuer_concentration.coverage_status.value == "complete"
    assert core_client.calls[0]["security_ids"] == ["A", "B"]


@pytest.mark.asyncio
async def test_engine_characterization_core_only_ignores_caller_mapping() -> None:
    request = ConcentrationRequest.model_validate(
        {
            **_stateless_payload(),
            "enrichment_policy": "core_only",
        }
    )
    core_client = _CoreEnrichmentRecorder(
        records=[
            {"security_id": "A", "issuer_id": "CORE_A"},
            {"security_id": "B", "issuer_id": "CORE_B"},
        ]
    )

    response = await calculate_concentration(request, core_client=core_client)

    assert response.issuer_concentration.hhi_current == 5200.0
    assert response.issuer_concentration.coverage_status.value == "complete"


@pytest.mark.asyncio
async def test_engine_characterization_ultimate_parent_grouping_collapses_issuers() -> None:
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "stateless",
            "issuer_grouping_level": "ultimate_parent",
            "enrichment_policy": "use_caller_only",
            "stateless_input": {
                "current_positions": [
                    {
                        "security_id": "A",
                        "quantity": 60,
                        "issuer_id": "ISSUER_A",
                        "ultimate_parent_issuer_id": "PARENT_X",
                    },
                    {
                        "security_id": "B",
                        "quantity": 40,
                        "issuer_id": "ISSUER_B",
                        "ultimate_parent_issuer_id": "PARENT_X",
                    },
                ],
                "projected_positions": [],
            },
        }
    )
    core_client = _CoreEnrichmentRecorder(records=[])

    response = await calculate_concentration(request, core_client=core_client)

    assert response.issuer_concentration.hhi_current == 10000.0
    assert response.issuer_concentration.covered_position_count_current == 2
    assert core_client.calls == []
