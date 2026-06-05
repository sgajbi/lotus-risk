from app.contracts.capabilities import (
    CAPABILITY_FEATURE_KEYS,
    CAPABILITY_WORKFLOW_KEYS,
    CapabilityFeature,
    CapabilityWorkflow,
    IntegrationCapabilitiesResponse,
)
from app.services.capability_workflows import build_capability_workflows


def test_capability_feature_keys_follow_risk_analytics_namespace() -> None:
    assert CAPABILITY_FEATURE_KEYS
    for key in CAPABILITY_FEATURE_KEYS:
        assert key.startswith(("risk.analytics.", "risk.observability."))


def test_capability_workflow_keys_use_snake_case_domain_vocabulary() -> None:
    assert CAPABILITY_WORKFLOW_KEYS
    for workflow_key in CAPABILITY_WORKFLOW_KEYS:
        assert workflow_key == workflow_key.lower()
        assert "-" not in workflow_key


def test_integration_capabilities_response_contract() -> None:
    payload = IntegrationCapabilitiesResponse(
        source_service="lotus-risk",
        policy_version="risk.v1",
        supported_input_modes=["stateless", "stateful", "simulation"],
        features=[CapabilityFeature(key=CAPABILITY_FEATURE_KEYS[0])],
        workflows=[
            CapabilityWorkflow(
                workflow_key=CAPABILITY_WORKFLOW_KEYS[0],
                endpoint_path="/analytics/risk/calculate",
                supported_input_modes=["stateless", "stateful"],
                support_status="full",
                notes=["simulation is intentionally unsupported"],
            )
        ],
    ).model_dump()
    assert payload["source_service"] == "lotus-risk"
    assert payload["policy_version"] == "risk.v1"
    assert payload["supported_input_modes"] == ["stateless", "stateful", "simulation"]
    assert payload["workflows"][0]["workflow_key"] == CAPABILITY_WORKFLOW_KEYS[0]
    assert payload["workflows"][0]["endpoint_path"] == "/analytics/risk/calculate"
    assert payload["workflows"][0]["support_status"] == "full"


def test_capability_workflow_catalog_covers_declared_workflow_keys_once() -> None:
    workflows = build_capability_workflows()
    workflow_keys = [workflow.workflow_key for workflow in workflows]

    assert workflow_keys == list(CAPABILITY_WORKFLOW_KEYS)
    assert len(workflow_keys) == len(set(workflow_keys))


def test_capability_workflow_catalog_preserves_support_boundaries() -> None:
    workflows = {
        workflow.workflow_key: workflow.model_dump() for workflow in build_capability_workflows()
    }

    assert workflows["risk_snapshot"]["supported_input_modes"] == ["stateless", "stateful"]
    assert workflows["risk_snapshot"]["support_status"] == "full"
    assert "simulation is intentionally unsupported" in workflows["risk_snapshot"]["notes"]

    concentration = workflows["concentration_risk"]
    assert concentration["supported_input_modes"] == ["stateless", "stateful", "simulation"]
    assert concentration["support_status"] == "full"
    assert any("only for concentration risk" in note for note in concentration["notes"])

    historical = workflows["historical_risk_attribution"]
    assert historical["support_status"] == "partial"
    assert any("issuer active-risk" in note for note in historical["notes"])


def test_capability_workflow_catalog_returns_independent_note_lists() -> None:
    first = build_capability_workflows()
    first[0].notes.append("mutated")

    second = build_capability_workflows()

    assert "mutated" not in second[0].notes
