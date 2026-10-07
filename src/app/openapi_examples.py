from typing import Any

from app.contracts.downstream_authority import (
    INVALID_TENANT_AUTHORITY_CODE,
    MAX_TENANT_ID_LENGTH,
    MISSING_TENANT_AUTHORITY_CODE,
    TENANT_ID_HEADER,
)
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


def _enterprise_authorization_extension(*, verified_pilot: bool) -> JsonObject:
    return {
        "x-lotus-enterprise-authorization": {
            "mode": "local_dev_header_trust",
            "enforced_when": (
                "LOTUS_RISK_PRINCIPAL_POSTURE=header-trust and ENTERPRISE_ENFORCE_AUTHZ=true"
            ),
            "permitted_environments": ["local", "dev"],
            "required_context_headers": list(ENTERPRISE_AUTHORIZATION_REQUIRED_HEADERS),
            "service_identity_headers": list(ENTERPRISE_SERVICE_IDENTITY_HEADERS),
            "trusted_ingress_header": TRUSTED_INGRESS_HEADER,
            "capabilities_header": ENTERPRISE_CAPABILITIES_HEADER,
            "capability_rules_env": "ENTERPRISE_CAPABILITY_RULES_JSON",
            "denial_status": 403,
            "denial_code": "AUTHORIZATION_DENIED",
            "denial_reason": "authorization_policy_denied",
        },
        "x-lotus-verified-principal": {
            "posture_env": "LOTUS_RISK_PRINCIPAL_POSTURE",
            "enforced_when": "LOTUS_RISK_PRINCIPAL_POSTURE=verified",
            "adopted": verified_pilot,
            "credential_header": "Authorization",
            "credential_scheme": "Bearer",
            "signature_algorithm": "EdDSA",
            "trusted_key_type": "OKP/Ed25519",
            "authority_headers_ignored": True,
            "providers": "deployment-injected verifier, revocation and GrantStore",
            "capability_rules_env": "ENTERPRISE_CAPABILITY_RULES_JSON",
            "delegated_authority": "user/application capability and portfolio intersection",
            "denial_code": "AUTHORIZATION_DENIED",
            "denial_statuses": [401, 403, 503] if verified_pilot else [403],
            "unadopted_route_reason": None if verified_pilot else "capability_not_granted",
            "production_iam_certified": False,
        },
    }


def _stateful_tenant_header_parameter(*, verified_pilot: bool) -> JsonObject:
    verified_description = (
        (
            "With LOTUS_RISK_PRINCIPAL_POSTURE=verified, tenant authority comes from the resolved "
            "credential and X-Tenant-Id is ignored in every input mode; the credential tenant is "
            "forwarded on tenant-owned downstream requests. In local/dev header-trust posture: "
        )
        if verified_pilot
        else ""
    )
    stateless_description = (
        "Stateless header-trust requests do not require tenant authority."
        if verified_pilot
        else "Stateless requests do not require tenant authority."
    )
    return {
        "name": TENANT_ID_HEADER,
        "in": "header",
        "required": False,
        "description": verified_description
        + (
            "Admitted tenant authority for stateful (and concentration simulation) input "
            "modes. The admitted value is forwarded on every tenant-owned lotus-performance "
            "and lotus-core request, including async status/result polling. A stateful "
            f"request without a non-blank value refuses with 401 {MISSING_TENANT_AUTHORITY_CODE} "
            "before any upstream request is made; a trimmed value longer than "
            f"{MAX_TENANT_ID_LENGTH} characters refuses with 400 {INVALID_TENANT_AUTHORITY_CODE}. "
        )
        + stateless_description,
        "schema": {
            "type": "string",
            "minLength": 1,
            "maxLength": MAX_TENANT_ID_LENGTH,
        },
        "example": "tenant-sg",
    }


def stateful_request_openapi_extra(
    examples: dict[str, JsonObject], *, verified_pilot: bool = False
) -> JsonObject:
    return {
        **request_body_examples(examples, verified_pilot=verified_pilot),
        "parameters": [_stateful_tenant_header_parameter(verified_pilot=verified_pilot)],
    }


def request_body_examples(
    examples: dict[str, JsonObject], *, verified_pilot: bool = False
) -> JsonObject:
    return {
        **_enterprise_authorization_extension(verified_pilot=verified_pilot),
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
    "stateful_request_openapi_extra",
]
