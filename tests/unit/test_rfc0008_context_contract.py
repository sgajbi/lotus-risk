from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_rfc0008_records_final_slice_and_guidance_assessment() -> None:
    rfc = (
        REPO_ROOT
        / "docs"
        / "rfcs"
        / "RFC-0008-enterprise-bank-readiness-and-live-risk-validation-baseline.md"
    ).read_text(encoding="utf-8")

    assert "Status: Done for lotus-risk scope" in rfc
    assert "## Skills and Guidance Assessment" in rfc
    assert "Slice 7 now updates repository context" in rfc
    assert "unrestricted enterprise-bank production approval remains conditional" in rfc
    assert "Needs lineage slice" not in rfc
    assert "Needs observability slice" not in rfc
    assert "Documentation and agent context | Partial" not in rfc


def test_repository_context_preserves_rfc0008_operating_truth() -> None:
    context = (REPO_ROOT / "REPOSITORY-ENGINEERING-CONTEXT.md").read_text(encoding="utf-8")

    assert "RFC-0008 establishes the current enterprise-readiness baseline" in context
    assert "http://localhost:8130" in context
    assert "http://localhost:8002" in context
    assert "http://localhost:8202" in context
    assert "concentration-only simulation support" in context
    assert "ACTIVE_RISK + ISSUER" in context


def test_risk_analytics_contract_records_final_simulation_mode_decisions() -> None:
    contract = (REPO_ROOT / "docs" / "standards" / "risk-analytics-contract.md").read_text(
        encoding="utf-8"
    )

    assert "reserved/not yet implemented" not in contract
    assert "reserved and not implemented" not in contract
    assert "concentration is the only simulation-enabled risk flow" in contract
    assert contract.count("simulation`: intentionally unsupported by contract") == 4


def test_rfc0009_records_enterprise_risk_intelligence_plan() -> None:
    rfc = (
        REPO_ROOT / "docs" / "rfcs" / "RFC-0009-enterprise-risk-intelligence-operating-layer.md"
    ).read_text(encoding="utf-8")

    assert "Status** | DRAFT - GOLD-STANDARD IMPLEMENTATION PLAN" in rfc
    assert "RiskIntelligenceEvidencePacket:v1" in rfc
    assert "RiskBriefLens:v1" in rfc
    assert "RiskAttentionEvent:v1" in rfc
    assert "CioScenarioLabRun:v1" in rfc
    assert "RiskModelGovernanceEvidence:v1" in rfc
    assert "No Second-Wave Rule" in rfc
    assert "Same-RFC Upstream and Downstream Change Rule" in rfc
    assert "Data Product and Data Mesh Target Posture" in rfc
    assert "Slice 1: Platform Automation and Scaffolding Improvement" in rfc
    assert "Slice 9: Grounded AI Risk Commentary and Guardrails" in rfc
    assert "Slice 10: Data Product and Platform Hardening" in rfc
    assert "Slice 14: Model-Risk Governance Evidence Center" in rfc
    assert (
        "Slice 16: Implementation Proof, Live Validation, and Portfolio Archetype Expansion" in rfc
    )
    assert "Slice 18: Second-Last Hardening and Review" in rfc
    assert "Slice 19: Final Closure, Mainline Truth, Documentation, and Branch Hygiene" in rfc
    assert "Slice 20: Post-Completion Communication" in rfc
    assert "Slice Evidence Ledger" in rfc
    assert "lotus-linkedin-thought-leadership" in rfc
    assert "No-WTBD Execution Rule" in rfc
