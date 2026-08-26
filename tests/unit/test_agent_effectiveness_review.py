from pathlib import Path

import pytest

pytestmark = pytest.mark.governance


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


def test_second_effectiveness_review_records_configuration_and_context_improvements() -> None:
    text = REVIEW.read_text(encoding="utf-8")

    assert "## 2026-06-07 Review 2" in text
    assert "docs/configuration.md" in text
    assert "fail-fast downstream URL policy" in text
    assert "A new standalone configuration gate would duplicate tested behavior" in text


def test_third_effectiveness_review_records_problem_details_and_modularity_evidence() -> None:
    text = REVIEW.read_text(encoding="utf-8")

    assert "## 2026-06-08 Review 3" in text
    assert "additive RFC 7807/problem-details compatibility" in text
    assert "service-hotspot extraction evidence" in text
    assert "problem-details metadata must remain additive" in text


def test_fourth_effectiveness_review_records_recent_modularity_evidence() -> None:
    text = REVIEW.read_text(encoding="utf-8")

    assert "## 2026-06-08 Review 4" in text
    assert "rolling period/source extraction" in text
    assert "risk period-result extraction" in text
    assert "risk benchmark-metric extraction" in text
    assert "did not change repository responsibilities" in text


def test_fifth_effectiveness_review_records_current_refactor_loop_evidence() -> None:
    text = REVIEW.read_text(encoding="utf-8")

    assert "## 2026-06-12 Review 5" in text
    assert "49 pushed commits" in text
    assert "transient facade-export/type issue and stale-import issue" in text
    assert "Repository role, canonical commands, runtime integration posture" in text
    assert "No new gate" in text
