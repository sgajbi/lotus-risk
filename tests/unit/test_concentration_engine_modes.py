from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pytest

from app.contracts.concentration import ConcentrationRequest
from app.services.concentration import parsing as concentration_parsing
from app.services.concentration.resolvers import resolve_simulation, resolve_stateful
from app.services.concentration_engine import calculate_concentration


class _RecordingCoreClient:
    def __init__(self) -> None:
        self.create_response: dict[str, object] = {}
        self.changes_response: dict[str, object] = {"version": 3}
        self.snapshot_response: dict[str, object] = {}
        self.last_snapshot_payload: dict[str, object] | None = None

    async def create_simulation_session(
        self,
        *,
        portfolio_id: str,
        ttl_hours: int | None,
        created_by: str | None,
        correlation_id: str | None,
    ) -> dict[str, object]:
        return self.create_response

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, object]],
        correlation_id: str | None,
    ) -> dict[str, object]:
        return self.changes_response

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        self.last_snapshot_payload = request_payload
        return self.snapshot_response

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {
            "records": [
                {"security_id": security_id, "issuer_id": f"ISSUER_{security_id}"}
                for security_id in security_ids
            ]
        }


@pytest.mark.asyncio
async def test_stateful_mode_includes_reporting_currency_and_metadata() -> None:
    client = _RecordingCoreClient()
    client.snapshot_response = {
        "valuation_context": {"portfolio_currency": "EUR", "reporting_currency": "USD"},
        "sections": {
            "positions_baseline": [
                {"security_id": "SEC_A", "market_value_base": "80"},
                {"security_id": "SEC_B", "market_value_base": "20"},
            ]
        },
    }
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "stateful",
            "stateful_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "reporting_currency": "USD",
            },
        }
    )

    response = await calculate_concentration(
        request, core_client=client, correlation_id="corr-stateful-unit"
    )

    assert response.metadata is not None
    assert response.metadata.portfolio_id == "DEMO_DPM_EUR_001"
    assert response.metadata.correlation_id == "corr-stateful-unit"
    assert response.metadata.issuer_grouping_level.value == "ultimate_parent"
    assert response.metadata.enrichment_policy.value == "merge_caller_then_core"
    assert response.metadata.include_cash_positions is True
    assert response.metadata.include_zero_quantity_positions is False
    assert response.risk_proxy.hhi_current == 6800.0
    assert client.last_snapshot_payload is not None
    assert client.last_snapshot_payload["reporting_currency"] == "USD"


@pytest.mark.asyncio
async def test_stateless_legal_issuer_core_enrichment_branch() -> None:
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "stateless",
            "issuer_grouping_level": "legal_issuer",
            "stateless_input": {
                "current_positions": [{"security_id": "A", "quantity": 60}],
                "projected_positions": [{"security_id": "A", "proposed_quantity": 40}],
            },
        }
    )

    response = await calculate_concentration(request, core_client=_RecordingCoreClient())

    assert response.issuer_concentration.covered_position_count_current == 1
    assert response.issuer_concentration.covered_position_count_proposed == 1


@pytest.mark.asyncio
async def test_stateful_mode_requires_sections_dict() -> None:
    client = _RecordingCoreClient()
    client.snapshot_response = {}
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "stateful",
            "stateful_input": {"portfolio_id": "DEMO_DPM_EUR_001", "as_of_date": "2026-02-27"},
        }
    )
    with pytest.raises(ValueError, match="stateful snapshot missing sections"):
        await calculate_concentration(request, core_client=client)


@pytest.mark.asyncio
async def test_stateful_resolver_requires_stateful_input() -> None:
    request = ConcentrationRequest.model_construct(
        input_mode="stateful",
        stateless_input=None,
        stateful_input=None,
        simulation_input=None,
    )

    with pytest.raises(ValueError, match="stateful_input is required"):
        await resolve_stateful(request, core_client=_RecordingCoreClient(), correlation_id=None)


@pytest.mark.asyncio
async def test_simulation_mode_invalid_create_session_response() -> None:
    client = _RecordingCoreClient()
    client.create_response = {"session": "bad"}
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "simulation_changes": [],
            },
        }
    )
    with pytest.raises(ValueError, match="invalid response payload"):
        await calculate_concentration(request, core_client=client)


@pytest.mark.asyncio
async def test_simulation_mode_requires_session_id_in_create_response() -> None:
    client = _RecordingCoreClient()
    client.create_response = {"session": {"version": 1}}
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "simulation_changes": [],
            },
        }
    )
    with pytest.raises(ValueError, match="missing session_id"):
        await calculate_concentration(request, core_client=client)


@pytest.mark.asyncio
async def test_simulation_mode_falls_back_to_baseline_and_parses_metadata() -> None:
    client = _RecordingCoreClient()
    client.create_response = {
        "session": {
            "session_id": "SIM_0001",
            "version": "2",
            "expires_at": "2026-02-28T10:30:00Z",
        }
    }
    client.changes_response = {"version": "3"}
    client.snapshot_response = {
        "valuation_context": {"portfolio_currency": "EUR", "position_basis": "market_value_base"},
        "simulation": {"version": "4"},
        "sections": {
            "positions_baseline": [{"security_id": "SEC_A", "market_value_base": "100"}],
            "positions_projected": [],
        },
    }
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "reporting_currency": "USD",
                "simulation_changes": [{"security_id": "SEC_A", "transaction_type": "BUY"}],
            },
        }
    )

    response = await calculate_concentration(
        request,
        core_client=client,
        correlation_id="corr-sim-unit",
        actor_id="tester",
    )

    assert response.metadata is not None
    assert response.metadata.simulation_session_id == "SIM_0001"
    assert response.metadata.correlation_id == "corr-sim-unit"
    assert response.metadata.simulation_session_version == 4
    assert isinstance(response.metadata.session_expires_at, datetime)
    assert response.metadata.issuer_grouping_level.value == "ultimate_parent"
    assert response.metadata.enrichment_policy.value == "merge_caller_then_core"
    assert response.metadata.include_cash_positions is True
    assert response.metadata.include_zero_quantity_positions is False
    assert response.risk_proxy.hhi_current == response.risk_proxy.hhi_proposed
    assert client.last_snapshot_payload is not None
    assert client.last_snapshot_payload["reporting_currency"] == "USD"


@pytest.mark.asyncio
async def test_simulation_mode_reuses_existing_session_without_snapshot_version() -> None:
    client = _RecordingCoreClient()
    client.snapshot_response = {
        "sections": {
            "positions_baseline": [{"security_id": "SEC_A", "market_value_base": "100"}],
            "positions_projected": [{"security_id": "SEC_A", "market_value_base": "80"}],
            "instrument_enrichment": [{"security_id": "SEC_A", "issuer_id": "ISSUER_A"}],
        },
    }
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "session_id": "SIM_EXISTING",
                "start_new_session": False,
                "simulation_changes": [],
            },
        }
    )

    response = await calculate_concentration(request, core_client=client)

    assert response.metadata is not None
    assert response.metadata.simulation_session_id == "SIM_EXISTING"
    assert response.metadata.simulation_session_version is None
    assert client.last_snapshot_payload is not None
    assert client.last_snapshot_payload["simulation"] == {"session_id": "SIM_EXISTING"}


@pytest.mark.asyncio
async def test_simulation_mode_requires_sections_dict() -> None:
    client = _RecordingCoreClient()
    client.create_response = {"session": {"session_id": "SIM_0001"}}
    client.snapshot_response = {"simulation": {"version": 2}}
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "simulation_changes": [],
            },
        }
    )
    with pytest.raises(ValueError, match="simulation snapshot missing sections"):
        await calculate_concentration(request, core_client=client)


@pytest.mark.asyncio
async def test_simulation_resolver_requires_simulation_input() -> None:
    request = ConcentrationRequest.model_construct(
        input_mode="simulation",
        stateless_input=None,
        stateful_input=None,
        simulation_input=None,
    )

    with pytest.raises(ValueError, match="simulation_input is required"):
        await resolve_simulation(
            request,
            core_client=_RecordingCoreClient(),
            correlation_id=None,
            actor_id=None,
        )


@pytest.mark.asyncio
async def test_stateful_and_simulation_modes_require_core_client() -> None:
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "stateful",
            "stateful_input": {"portfolio_id": "DEMO_DPM_EUR_001", "as_of_date": "2026-02-27"},
        }
    )
    with pytest.raises(ValueError, match="lotus-core client is required"):
        await calculate_concentration(request)


@pytest.mark.asyncio
async def test_unsupported_mode_guard_branch() -> None:
    request = ConcentrationRequest.model_construct(
        input_mode="unsupported",
        stateless_input=None,
        stateful_input=None,
        simulation_input=None,
    )
    with pytest.raises(ValueError, match="Unsupported concentration input_mode"):
        await calculate_concentration(request, core_client=_RecordingCoreClient())


def test_helper_branches_for_type_conversion() -> None:
    assert concentration_parsing._extract_valuation_context(None) is None
    assert concentration_parsing._as_int("12") == 12
    assert concentration_parsing._as_datetime(None) is None
    assert concentration_parsing._as_datetime("not-a-date") is None
    mixed_positions: list[Any] = [
        None,
        {"security_id": "A", "market_value_base": "bad"},
        {"security_id": "B", "quantity": "7.5"},
    ]
    values = concentration_parsing._extract_values_from_snapshot_positions(
        cast(list[dict[str, Any]], mixed_positions)
    )
    assert values == [7.5]
