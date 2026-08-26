from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from app.evidence.idea_opportunity_constants import CANONICAL_AS_OF_DATE
from app.evidence.idea_opportunity_runtime import (
    build_idea_opportunity_runtime_evidence,
    idea_opportunity_runtime_evidence_is_valid,
)
from app.main import app
from tests.support.app_runtime import override_app_runtime
from tests.support.lotus_core_fakes import SimulationLotusCoreClient
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import build_returns_series_response

_CANONICAL_RETURN_ROWS = (
    ("2026-04-06", "0.015"),
    ("2026-04-07", "-0.028"),
    ("2026-04-08", "0.011"),
    ("2026-04-09", "-0.016"),
    ("2026-04-10", "0.004"),
)
_CANONICAL_BENCHMARK_ROWS = (
    ("2026-04-06", "0.004"),
    ("2026-04-07", "-0.005"),
    ("2026-04-08", "0.003"),
    ("2026-04-09", "-0.004"),
    ("2026-04-10", "0.001"),
)


class _CanonicalCoreClient(SimulationLotusCoreClient):
    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        snapshot = await super().get_core_snapshot(
            portfolio_id=portfolio_id,
            request_payload=request_payload,
            correlation_id=correlation_id,
        )
        sections = snapshot.setdefault("sections", {})
        assert isinstance(sections, dict)
        sections["instrument_enrichment"] = [
            {
                "security_id": "SEC_A",
                "issuer_id": "SOURCE_SAFE_ISSUER_A",
                "ultimate_parent_issuer_id": "SOURCE_SAFE_PARENT_ISSUER_A",
            },
            {
                "security_id": "SEC_B",
                "issuer_id": "SOURCE_SAFE_ISSUER_A",
                "ultimate_parent_issuer_id": "SOURCE_SAFE_PARENT_ISSUER_A",
            },
        ]
        return snapshot


def test_idea_opportunity_runtime_evidence_executes_live_api_routes() -> None:
    client = TestClient(app)
    performance_client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=_CANONICAL_RETURN_ROWS,
            benchmark_returns=_CANONICAL_BENCHMARK_ROWS,
        )
    )
    core_client = _CanonicalCoreClient(
        session_id="SIM_IDEA_EVIDENCE",
        simulation_version=1,
        include_ultimate_parent_issuer_id=True,
    )
    seen_payloads: list[Mapping[str, Any]] = []

    def execute(route: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        seen_payloads.append(payload)
        response = client.post(route, json=payload)
        return response.status_code, response.json()

    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
        evidence = build_idea_opportunity_runtime_evidence(
            execute=execute,
            generated_at_utc=datetime(2026, 7, 23, 6, 30, tzinfo=UTC),
        )

    assert idea_opportunity_runtime_evidence_is_valid(evidence) is True
    assert [execution["receipt"]["route"] for execution in evidence["executions"]] == [
        "/analytics/risk/concentration",
        "/analytics/risk/calculate",
        "/analytics/risk/drawdown",
    ]
    assert [payload["input_mode"] for payload in seen_payloads] == [
        "stateful",
        "stateful",
        "stateful",
    ]
    assert all(
        payload["stateful_input"]["as_of_date"] == CANONICAL_AS_OF_DATE.isoformat()
        for payload in seen_payloads
    )
    assert all(
        execution["receipt"]["freshnessBucket"] == "current" for execution in evidence["executions"]
    )
    assert all(execution["receipt"]["summary"] for execution in evidence["executions"])
