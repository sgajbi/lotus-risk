from typing import Any

from app.enterprise_authorization import (
    ENTERPRISE_AUTHORIZATION_REQUIRED_HEADERS,
    ENTERPRISE_CAPABILITIES_HEADER,
    ENTERPRISE_SERVICE_IDENTITY_HEADERS,
)
from app.enterprise_trusted_ingress import TRUSTED_INGRESS_HEADER
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


def _enterprise_authorization_extension() -> JsonObject:
    return {
        "x-lotus-enterprise-authorization": {
            "mode": "enterprise_bank_deployment",
            "enforced_when": "ENTERPRISE_ENFORCE_AUTHZ=true",
            "required_context_headers": list(ENTERPRISE_AUTHORIZATION_REQUIRED_HEADERS),
            "service_identity_headers": list(ENTERPRISE_SERVICE_IDENTITY_HEADERS),
            "trusted_ingress_header": TRUSTED_INGRESS_HEADER,
            "capabilities_header": ENTERPRISE_CAPABILITIES_HEADER,
            "capability_rules_env": "ENTERPRISE_CAPABILITY_RULES_JSON",
            "denial_status": 403,
            "denial_code": "AUTHORIZATION_DENIED",
            "denial_reason": "authorization_policy_denied",
        }
    }


def request_body_examples(examples: dict[str, JsonObject]) -> JsonObject:
    return {
        **_enterprise_authorization_extension(),
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {name: {"value": value} for name, value in examples.items()}
                }
            }
        },
    }


__all__ = [
    "CONCENTRATION_EXAMPLES",
    "DRAWDOWN_EXAMPLES",
    "HISTORICAL_ATTRIBUTION_EXAMPLES",
    "MANDATE_HEALTH_EXAMPLES",
    "REGIME_SCENARIO_EXAMPLES",
    "RISK_CALCULATE_EXAMPLES",
    "RISK_EVENT_COHORT_EXAMPLES",
    "ROLLING_METRICS_EXAMPLES",
    "JsonObject",
    "request_body_examples",
]
