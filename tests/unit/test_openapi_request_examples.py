from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.contracts.attribution import HistoricalAttributionRequest
from app.contracts.concentration import ConcentrationRequest
from app.contracts.drawdown import DrawdownAnalyticsRequest
from app.contracts.mandate_health import MandateRiskHealthContextRequest
from app.contracts.risk import RiskAnalyticsRequest
from app.contracts.risk_event_cohort import RiskEventAffectedCohortRequest
from app.contracts.rolling import RollingAnalyticsRequest
from app.contracts.scenario import RegimeScenarioPackRequest
from app.main import app
from app.openapi_examples import (
    CONCENTRATION_EXAMPLES,
    DRAWDOWN_EXAMPLES,
    HISTORICAL_ATTRIBUTION_EXAMPLES,
    MANDATE_HEALTH_EXAMPLES,
    REGIME_SCENARIO_EXAMPLES,
    RISK_CALCULATE_EXAMPLES,
    RISK_EVENT_COHORT_EXAMPLES,
    ROLLING_METRICS_EXAMPLES,
)

EXAMPLE_MODELS: tuple[
    tuple[str, type[BaseModel], Mapping[str, dict[str, Any]]],
    ...,
] = (
    ("risk/calculate", RiskAnalyticsRequest, RISK_CALCULATE_EXAMPLES),
    ("drawdown", DrawdownAnalyticsRequest, DRAWDOWN_EXAMPLES),
    ("rolling-metrics", RollingAnalyticsRequest, ROLLING_METRICS_EXAMPLES),
    ("concentration", ConcentrationRequest, CONCENTRATION_EXAMPLES),
    ("historical-attribution", HistoricalAttributionRequest, HISTORICAL_ATTRIBUTION_EXAMPLES),
    ("mandate-health-context", MandateRiskHealthContextRequest, MANDATE_HEALTH_EXAMPLES),
    ("regime-scenario-pack", RegimeScenarioPackRequest, REGIME_SCENARIO_EXAMPLES),
    ("risk-event-cohort", RiskEventAffectedCohortRequest, RISK_EVENT_COHORT_EXAMPLES),
)


@pytest.mark.parametrize(("endpoint", "request_model", "examples"), EXAMPLE_MODELS)
def test_openapi_request_examples_validate_against_request_models(
    endpoint: str,
    request_model: type[BaseModel],
    examples: Mapping[str, dict[str, Any]],
) -> None:
    for example_name, example_payload in examples.items():
        validated = request_model.model_validate(example_payload)
        assert isinstance(validated, request_model), f"{endpoint}:{example_name}"


def test_post_routes_publish_request_body_examples() -> None:
    spec = TestClient(app).get("/openapi.json").json()

    for path, path_item in spec["paths"].items():
        post_operation = path_item.get("post")
        if post_operation is None:
            continue
        examples = (
            post_operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("examples", {})
        )
        assert examples, f"{path} is missing request examples"
