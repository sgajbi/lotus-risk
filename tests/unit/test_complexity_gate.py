"""`complexity-gate` must be able to fail.

It used to be `radon cc` and `radon mi`, neither of which accepts a failure threshold, wired into the
blocking `ci` lane beside three gates that do fail. Complexity could regress without limit and the
lane stayed green, with nothing in the output to tell it apart from a gate that was enforcing
something. See issue #225.

These tests pin the two properties that made it not-a-gate: that a breach returns non-zero, and that
the declared thresholds equal the measured tree with no headroom.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.python_complexity_inventory import (
    HIGH_COMPLEXITY_RANKS,
    MEDIUM_COMPLEXITY_RANKS,
    ComplexityFinding,
    collect_complexity,
    complexity_gate_failures,
    parse_complexity_payload,
    rank_count,
)

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"


def _finding(complexity: int, rank: str) -> ComplexityFinding:
    return ComplexityFinding(
        path="src/app/m.py", name="f", kind="function", rank=rank, complexity=complexity, line=1
    )


def _declared_thresholds() -> dict[str, int]:
    target = re.search(
        r"^complexity-gate:\n(?:\t.*\n)+", MAKEFILE.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert target is not None, "complexity-gate is no longer defined in the Makefile"
    return {
        flag: int(value)
        for flag, value in re.findall(
            r"--(max-cc|max-high-complexity|max-medium-complexity) (\d+)", target.group(0)
        )
    }


def test_the_gate_target_no_longer_runs_a_command_that_cannot_fail() -> None:
    """`radon cc` and `radon mi` exit 0 whatever they print; `-n C` filters output, not status."""

    target = re.search(
        r"^complexity-gate:\n(?:\t.*\n)+", MAKEFILE.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert target is not None
    recipe = target.group(0)

    assert "radon" not in recipe, (
        "complexity-gate invokes radon directly again. radon has no failing exit code in any mode, "
        "so the target would report success whatever the tree contains. See issue #225."
    )
    assert "python_complexity_inventory.py" in recipe


def test_a_complexity_rise_above_the_banked_maximum_fails() -> None:
    findings = [_finding(25, "D"), _finding(3, "A")]

    failures = complexity_gate_failures(findings, max_cc=24, max_high_complexity=1)

    assert len(failures) == 1
    assert "25 exceeds allowed 24" in failures[0]


def test_the_banked_maximum_itself_passes() -> None:
    """A ratchet is banked at exact equality, so the measured value must not fail."""

    findings = [_finding(24, "D"), _finding(3, "A")]

    assert complexity_gate_failures(findings, max_cc=24, max_high_complexity=1) == []


def test_an_extra_high_complexity_block_fails_even_below_the_maximum() -> None:
    """The two thresholds catch different regressions: one deep block, or more deep blocks."""

    findings = [_finding(24, "D"), _finding(22, "D")]

    failures = complexity_gate_failures(findings, max_cc=24, max_high_complexity=1)

    assert len(failures) == 1
    assert "block count 2 exceeds allowed 1" in failures[0]


def test_an_empty_scan_fails_rather_than_reporting_a_clean_tree() -> None:
    """A gate that inspected nothing must fail. Silence is never a pass.

    The reference implementation this was ported from treats an empty result as a maximum of 0 and
    passes, so a renamed source root or a lane running from the wrong directory reports the
    cleanest possible tree. See `lotus-platform#738`.
    """

    failures = complexity_gate_failures([], max_cc=24, max_high_complexity=1)

    assert len(failures) == 1
    assert "empty scan is not a clean tree" in failures[0]


def test_a_file_radon_could_not_parse_is_an_error_not_a_skip() -> None:
    """Skipping an unparseable file would let it quietly reduce the measured maximum."""

    with pytest.raises(RuntimeError, match="could not analyse"):
        parse_complexity_payload({"src/app/broken.py": {"error": "invalid syntax"}})


def test_radon_emits_class_methods_as_top_level_findings_without_double_counting(
    tmp_path: Path,
) -> None:
    """Pin the Radon 6.0.1 payload shape the inventory deliberately consumes.

    Radon repeats a class method in the class entry's ``methods`` metadata and as a top-level
    finding. The inventory consumes top-level findings, so recursively flattening ``methods``
    would count every method twice and spend the rank-C ratchet incorrectly.
    """

    source = tmp_path / "class_with_complex_method.py"
    source.write_text(
        "class Holder:\n"
        "    def complex_method(self, value):\n"
        "        if value == 1:\n"
        "            return 1\n"
        "        if value == 2:\n"
        "            return 2\n"
        "        if value == 3:\n"
        "            return 3\n"
        "        if value == 4:\n"
        "            return 4\n"
        "        if value == 5:\n"
        "            return 5\n"
        "        if value == 6:\n"
        "            return 6\n"
        "        if value == 7:\n"
        "            return 7\n"
        "        if value == 8:\n"
        "            return 8\n"
        "        if value == 9:\n"
        "            return 9\n"
        "        if value == 10:\n"
        "            return 10\n"
        "        return 0\n",
        encoding="utf-8",
    )

    findings = collect_complexity((str(source),))
    methods = [finding for finding in findings if finding.name == "complex_method"]

    assert len(methods) == 1
    assert methods[0].kind == "method"
    assert methods[0].rank == "C"


def test_findings_are_ordered_so_the_first_is_the_worst() -> None:
    """`complexity_gate_failures` reads `findings[0]` as the observed maximum."""

    findings = parse_complexity_payload(
        {
            "src/a.py": [
                {"name": "low", "type": "function", "rank": "A", "complexity": 2, "lineno": 1}
            ],
            "src/b.py": [
                {"name": "high", "type": "function", "rank": "D", "complexity": 30, "lineno": 9}
            ],
        }
    )

    assert findings[0].name == "high"
    assert findings[0].complexity == 30


def test_rank_counting_covers_every_high_rank() -> None:
    findings = [_finding(30, "F"), _finding(25, "E"), _finding(21, "D"), _finding(9, "C")]

    assert rank_count(findings, HIGH_COMPLEXITY_RANKS) == 3


def test_the_declared_thresholds_equal_the_measured_tree() -> None:
    """Banked at exact equality: an allowance above the measurement is unbanked slack.

    This also fails if complexity *improves* without the threshold being re-banked downward, which
    is the half of ratchet discipline that is easy to skip.
    """

    declared = _declared_thresholds()
    assert set(declared) == {"max-cc", "max-high-complexity", "max-medium-complexity"}, declared

    findings = collect_complexity(("src",))
    assert findings, "collected no complexity findings; the gate would be measuring nothing"

    assert declared["max-cc"] == findings[0].complexity, (
        f"complexity-gate declares --max-cc {declared['max-cc']} but the tree measures "
        f"{findings[0].complexity}. Re-bank a ceiling downward in the change that improves it."
    )
    assert declared["max-high-complexity"] == rank_count(findings, HIGH_COMPLEXITY_RANKS), (
        f"complexity-gate declares --max-high-complexity {declared['max-high-complexity']} but the "
        f"tree measures {rank_count(findings, HIGH_COMPLEXITY_RANKS)}."
    )
    assert declared["max-medium-complexity"] == rank_count(findings, MEDIUM_COMPLEXITY_RANKS), (
        f"complexity-gate declares --max-medium-complexity "
        f"{declared['max-medium-complexity']} but the tree measures "
        f"{rank_count(findings, MEDIUM_COMPLEXITY_RANKS)}."
    )


def test_rank_c_growth_fails_even_when_the_maximum_holds() -> None:
    """Capping only D-F left rank C (complexity 11-20) unbanked.

    Any number of new rank-C blocks passed while the maximum stayed 24 and the D-F count stayed 1,
    so the pile could grow indefinitely with the gate green - the six existing C blocks were
    governed by nothing.
    """

    findings = [_finding(24, "D")] + [_finding(12, "C") for _ in range(7)]

    failures = complexity_gate_failures(
        findings, max_cc=24, max_high_complexity=1, max_medium_complexity=6
    )

    assert len(failures) == 1
    assert "rank C) block count 7 exceeds allowed 6" in failures[0]


def test_the_banked_rank_c_count_itself_passes() -> None:
    findings = [_finding(24, "D")] + [_finding(12, "C") for _ in range(6)]

    assert (
        complexity_gate_failures(
            findings, max_cc=24, max_high_complexity=1, max_medium_complexity=6
        )
        == []
    )


def test_the_wiki_documents_the_gate_and_the_renamed_report() -> None:
    """Operator documentation must match the commands that exist.

    `wiki/Validation-and-CI.md` described `make complexity-gate` as producing a maintainability
    report, which stopped being true when that output moved to its own target. A documented command
    that no longer behaves as described is the drift class `lotus-platform#734` exists for.
    """

    wiki = (ROOT / "wiki" / "Validation-and-CI.md").read_text(encoding="utf-8")

    assert "`make maintainability-report`" in wiki, (
        "the renamed maintainability command is not documented for operators"
    )
    declared = _declared_thresholds()
    for value in declared.values():
        assert f"`{value}`" in wiki, f"the wiki does not state the banked threshold {value}"
