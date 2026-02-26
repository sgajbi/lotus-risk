from app.contracts.capabilities import (
    CAPABILITY_FEATURE_KEYS,
    CAPABILITY_WORKFLOW_KEYS,
    CapabilityFeature,
    CapabilityWorkflow,
    IntegrationCapabilitiesResponse,
)


def test_capability_feature_keys_follow_risk_analytics_namespace() -> None:
    assert CAPABILITY_FEATURE_KEYS
    for key in CAPABILITY_FEATURE_KEYS:
        assert key.startswith("risk.analytics.")


def test_capability_workflow_keys_use_snake_case_domain_vocabulary() -> None:
    assert CAPABILITY_WORKFLOW_KEYS
    for workflow_key in CAPABILITY_WORKFLOW_KEYS:
        assert workflow_key == workflow_key.lower()
        assert "-" not in workflow_key


def test_integration_capabilities_response_alias_contract() -> None:
    payload = IntegrationCapabilitiesResponse(
        sourceService="lotus-risk",
        policyVersion="risk.v1",
        supportedInputModes=["api"],
        features=[CapabilityFeature(key=CAPABILITY_FEATURE_KEYS[0])],
        workflows=[CapabilityWorkflow(workflow_key=CAPABILITY_WORKFLOW_KEYS[0])],
    ).model_dump(by_alias=True)
    assert payload["sourceService"] == "lotus-risk"
    assert payload["policyVersion"] == "risk.v1"
    assert payload["supportedInputModes"] == ["api"]
    assert payload["workflows"][0]["workflow_key"] == CAPABILITY_WORKFLOW_KEYS[0]
