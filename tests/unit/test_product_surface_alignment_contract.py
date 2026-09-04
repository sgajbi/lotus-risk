from pathlib import Path
from typing import TypedDict

from fastapi.testclient import TestClient

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_DOCS = REPO_ROOT / "docs" / "domain-apis"


class CapabilityWorkflowPayload(TypedDict):
    workflow_key: str
    supported_input_modes: list[str]
    support_status: str
    notes: list[str]


def _capability_workflows() -> dict[str, CapabilityWorkflowPayload]:
    response = TestClient(app).get("/integration/capabilities")
    assert response.status_code == 200
    return {workflow["workflow_key"]: workflow for workflow in response.json()["workflows"]}


def test_product_surface_contract_keeps_simulation_concentration_only() -> None:
    workflows = _capability_workflows()

    assert workflows["concentration_risk"]["supported_input_modes"] == [
        "stateless",
        "stateful",
        "simulation",
    ]
    assert (
        "simulation is supported only for concentration risk"
        in workflows["concentration_risk"]["notes"]
    )
    for workflow_key in (
        "risk_snapshot",
        "drawdown_analytics",
        "rolling_risk_analytics",
        "historical_risk_attribution",
    ):
        workflow = workflows[workflow_key]
        assert workflow["supported_input_modes"] == ["stateless", "stateful"]
        assert any("simulation is intentionally unsupported" == note for note in workflow["notes"])


def test_product_surface_contract_supports_issuer_active_risk() -> None:
    workflows = _capability_workflows()
    attribution = workflows["historical_risk_attribution"]

    assert attribution["support_status"] == "partial"
    assert (
        "stateful active-risk supports POSITION, SECTOR, ASSET_CLASS, and ISSUER"
        in attribution["notes"]
    )
    assert (
        "issuer active-risk consumes lotus-performance benchmark exposure context issuer groups"
        in attribution["notes"]
    )
    assert (
        "historical-attribution response metadata is the authoritative active-risk support contract"
        in attribution["notes"]
    )
    assert (
        "attribution residual, reconciled_sum, and metadata.metric_unit_semantics must be preserved with contributors"
        in attribution["notes"]
    )


def test_product_surface_contract_exposes_signed_var_guidance() -> None:
    workflows = _capability_workflows()

    assert (
        "VaR and expected shortfall are signed return-threshold metrics"
        in workflows["risk_snapshot"]["notes"]
    )


def test_product_surface_alignment_doc_covers_downstream_truth_requirements() -> None:
    doc = (DOMAIN_DOCS / "risk-product-surface-alignment.md").read_text(encoding="utf-8")

    required_terms = (
        "signed return-threshold",
        "expected shortfall",
        "total_value",
        "reconciled_sum",
        "residual",
        "ACTIVE_RISK + ISSUER",
        "concentration-only",
        "request_fingerprint",
        "upstream_request_fingerprints",
        "coverage_status",
    )
    for term in required_terms:
        assert term in doc


def test_endpoint_docs_link_product_surface_alignment_contract() -> None:
    readme = (DOMAIN_DOCS / "README.md").read_text(encoding="utf-8")
    endpoint_matrix = (DOMAIN_DOCS / "endpoint-matrix.md").read_text(encoding="utf-8")
    capabilities = (DOMAIN_DOCS / "integration-capabilities.md").read_text(encoding="utf-8")

    assert "risk-product-surface-alignment.md" in readme
    assert "risk-product-surface-alignment.md" in endpoint_matrix
    assert "derive simulation and issuer active-risk affordances" in capabilities
    assert "authoritative active-risk support contract" in capabilities
    assert "signed return-threshold metrics" in capabilities
    assert (
        "residual, `reconciled_sum`, and `metadata.metric_unit_semantics` "
        "must be preserved" in capabilities
    )
