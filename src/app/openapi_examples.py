from typing import Any

from app.openapi_request_examples import (
    CONCENTRATION_EXAMPLES,
    DRAWDOWN_EXAMPLES,
    HISTORICAL_ATTRIBUTION_EXAMPLES,
    MANDATE_HEALTH_EXAMPLES,
    REGIME_SCENARIO_EXAMPLES,
    RISK_CALCULATE_EXAMPLES,
    RISK_EVENT_COHORT_EXAMPLES,
    ROLLING_METRICS_EXAMPLES,
)

JsonObject = dict[str, Any]


def request_body_examples(examples: dict[str, JsonObject]) -> JsonObject:
    return {
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {name: {"value": value} for name, value in examples.items()}
                }
            }
        }
    }


__all__ = [
    "CONCENTRATION_EXAMPLES",
    "DRAWDOWN_EXAMPLES",
    "HISTORICAL_ATTRIBUTION_EXAMPLES",
    "JsonObject",
    "MANDATE_HEALTH_EXAMPLES",
    "REGIME_SCENARIO_EXAMPLES",
    "RISK_CALCULATE_EXAMPLES",
    "RISK_EVENT_COHORT_EXAMPLES",
    "ROLLING_METRICS_EXAMPLES",
    "request_body_examples",
]
