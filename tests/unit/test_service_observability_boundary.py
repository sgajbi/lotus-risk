from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.contracts.risk import RiskCalculationSupportability
from app.services import calculation_supportability, endpoint_observation

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "src" / "app" / "services"
SANCTIONED_ADAPTER = "observability_ports.py"


class _ObservedEndpointResponse(BaseModel):
    status: str


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_only_observability_port_adapter_imports_concrete_observability_module() -> None:
    violations: list[str] = []
    for service_path in sorted(SERVICES_DIR.rglob("*.py")):
        if service_path.name == SANCTIONED_ADAPTER:
            continue
        imports = _imported_modules(service_path)
        if "app.observability" in imports:
            violations.append(service_path.relative_to(REPO_ROOT).as_posix())

    assert violations == []


def test_supportability_recording_uses_service_observability_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[tuple[str, dict[str, Any]]] = []

    def _record_calculation_supportability(**kwargs: Any) -> None:
        recorded.append(("calculation", kwargs))

    def _record_freshness_bucket(**kwargs: Any) -> None:
        recorded.append(("freshness", kwargs))

    monkeypatch.setattr(
        calculation_supportability,
        "record_calculation_supportability",
        _record_calculation_supportability,
    )
    monkeypatch.setattr(
        calculation_supportability,
        "record_analytics_freshness_bucket",
        _record_freshness_bucket,
    )

    calculation_supportability.record_operation_supportability(
        operation="risk/calculate",
        supportability=RiskCalculationSupportability(
            state="degraded",
            reason="calculation_quality_issue",
            freshness_bucket="stale",
        ),
    )

    assert recorded == [
        (
            "calculation",
            {
                "operation": "risk/calculate",
                "supportability_state": "degraded",
                "reason": "calculation_quality_issue",
                "freshness_bucket": "stale",
            },
        ),
        (
            "freshness",
            {
                "operation": "risk/calculate",
                "freshness_bucket": "stale",
                "supportability_state": "degraded",
            },
        ),
    ]


@pytest.mark.asyncio
async def test_endpoint_observation_uses_service_observability_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[dict[str, Any]] = []

    monkeypatch.setattr(endpoint_observation, "observation_start", lambda: 42.0)
    monkeypatch.setattr(
        endpoint_observation,
        "record_endpoint_execution",
        lambda **kwargs: recorded.append(kwargs),
    )

    result = await endpoint_observation.observed_endpoint(
        endpoint="risk/calculate",
        input_mode="stateless",
        operation=lambda: {"status": "ok"},
        response_model=_ObservedEndpointResponse,
    )

    assert result == _ObservedEndpointResponse(status="ok")
    assert recorded == [
        {
            "endpoint": "risk/calculate",
            "input_mode": "stateless",
            "outcome": "success",
            "started_at": 42.0,
        }
    ]


@pytest.mark.asyncio
async def test_endpoint_observation_records_response_model_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[dict[str, Any]] = []

    monkeypatch.setattr(endpoint_observation, "observation_start", lambda: 42.0)
    monkeypatch.setattr(
        endpoint_observation,
        "record_endpoint_execution",
        lambda **kwargs: recorded.append(kwargs),
    )

    with pytest.raises(ValidationError):
        await endpoint_observation.observed_endpoint(
            endpoint="risk/calculate",
            input_mode="stateless",
            operation=lambda: {"unexpected": "shape"},
            response_model=_ObservedEndpointResponse,
        )

    assert recorded == [
        {
            "endpoint": "risk/calculate",
            "input_mode": "stateless",
            "outcome": "failure",
            "started_at": 42.0,
        }
    ]
