from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_rfc0008_records_final_slice_and_guidance_assessment() -> None:
    rfc = (
        REPO_ROOT
        / "docs"
        / "rfcs"
        / "RFC-0008-enterprise-bank-readiness-and-live-risk-validation-baseline.md"
    ).read_text(encoding="utf-8")

    assert "Status: Implemented on feature branch" in rfc
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
