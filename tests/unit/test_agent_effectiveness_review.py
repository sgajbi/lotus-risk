from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW = REPO_ROOT / "quality" / "agent_effectiveness_review.md"
PLAYBOOK = REPO_ROOT / "docs" / "architecture" / "CODEBASE-REVIEW-PLAYBOOK.md"


def test_agent_effectiveness_review_records_all_required_areas() -> None:
    text = REVIEW.read_text(encoding="utf-8")

    for area in (
        "Skill routing",
        "Agent guidance",
        "Documentation",
        "Repository context",
        "Automation",
    ):
        assert f"| {area} |" in text


def test_codebase_review_playbook_requires_recurring_effectiveness_review() -> None:
    text = PLAYBOOK.read_text(encoding="utf-8")

    assert "After every five meaningful slices" in text
    assert "quality/agent_effectiveness_review.md" in text
    assert "deliberate no-change decision" in text
