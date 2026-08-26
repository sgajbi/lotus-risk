"""The wiki claims to list the repo-native commands, so it must list the gates that can fail.

`wiki/Validation-and-CI.md` publishes the validation commands contributors are told to run. It did
not name `github-actions-runtime-gate` - the *first* target in both `check` and `ci` - nor
`test-pyramid-gate`, `complexity-gate`, `dead-code-gate` or `dependency-hygiene-gate`. A contributor
whose build failed on any of them would find no explanation on the page that exists to explain it.

Nothing compared what the wiki claimed against what the lanes run, which is why it went stale
silently: the same documented-versus-enforced shape found repeatedly across this estate.

Elsewhere the durable fix was to stop restating and cite the source. That is not available here - a
wiki page is prose written for people and cannot point at a Make target and stay useful. So the copy
stays and is checked, which is the weaker of the two answers.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
WIKI = ROOT / "wiki" / "Validation-and-CI.md"


def _is_gate(target: str) -> bool:
    return target.endswith(("-gate", "-gates"))


def _resolved_make_database(makefile: str) -> str:
    environment = os.environ.copy()
    environment.pop("MAKEFLAGS", None)
    environment.pop("MFLAGS", None)
    result = subprocess.run(
        ["make", "--no-print-directory", "-rR", "-qp", "-f", "-"],
        input=makefile,
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=environment,
        check=False,
    )
    assert result.returncode in {0, 1}, (
        f"GNU Make could not resolve the gate dependency graph: {result.stderr.strip()}"
    )
    _, marker, files_section = result.stdout.partition("# Files")
    assert marker, "GNU Make database did not contain a Files section."
    return files_section.partition("# files hash-table stats:")[0]


def _target_dependencies(makefile: str) -> dict[str, list[str]]:
    dependencies: dict[str, list[str]] = {}
    for database_line in _resolved_make_database(makefile).splitlines():
        rule_match = re.match(
            r"^(?P<targets>[^:#][^:]*):[ \t]*(?P<prerequisites>.*)$", database_line
        )
        if rule_match is None:
            continue
        targets = rule_match.group("targets").split()
        prerequisite_text = rule_match.group("prerequisites")
        if re.match(
            r"^(?:(?:override|private|export|unexport)[ \t]+)?"
            r"[A-Za-z_][A-Za-z0-9_]*[ \t]*[?+:!]?=",
            prerequisite_text,
        ):
            continue  # GNU Make database record for a target-specific variable assignment.
        prerequisites = [
            prerequisite for prerequisite in prerequisite_text.split() if prerequisite != "|"
        ]
        for target in targets:
            dependencies.setdefault(target, []).extend(prerequisites)
    return dependencies


def _reachable_targets(makefile: str) -> set[str]:
    dependencies = _target_dependencies(makefile)
    for lane in ("check", "ci"):
        assert lane in dependencies, f"The {lane} lane is missing from the Makefile."
    pending = [target for lane in ("check", "ci") for target in dependencies[lane]]
    reachable: set[str] = set()
    while pending:
        target = pending.pop()
        if target in reachable:
            continue
        reachable.add(target)
        pending.extend(dependencies.get(target, []))
    return reachable


def _gate_targets() -> set[str]:
    """Every `*-gate` target reachable from the blocking lanes, including aggregate members."""

    reachable = {
        target
        for target in _reachable_targets(MAKEFILE.read_text(encoding="utf-8"))
        if _is_gate(target)
    }
    assert reachable, (
        "No gate targets found in the blocking lanes; this check would assert nothing."
    )
    return reachable


# Gate names as the wiki actually writes them: inside backticks, usually behind `make `. The
# first version omitted the optional `make ` prefix and so matched NOTHING - 0 of 13 backticked
# gate spellings on this page - which made the reverse check pass for every possible page
# content, including an injected `make totally-fictional-gate`. See lotus-render#77.
_WIKI_GATE_NAME = re.compile(r"`(?:make\s+)?([a-z0-9]+(?:-[a-z0-9]+)*-gates?)`")


def _stale_wiki_gates(wiki: str, makefile: str) -> list[str]:
    live = {target for target in _reachable_targets(makefile) if _is_gate(target)}
    named_in_wiki = {match.group(1) for match in _WIKI_GATE_NAME.finditer(wiki)}
    return sorted(name for name in named_in_wiki if name not in live)


def test_reachability_parses_continuations_without_reading_recipe_text() -> None:
    makefile = "check: aggregate-gate \\\n continued-gate # disabled-gate\ncheck: repeated-gate\nci: aggregate-gate ; @echo recipe-only-gate\naggregate-gate sibling-gate: multi-target-gate\naggregate-gate:\n\t@echo disabled-gate\ncontinued-gate:\n\tpython continued_check.py\nrepeated-gate:\n\tpython repeated_check.py\nmulti-target-gate:\n\tpython multi_target_check.py"

    reachable = _reachable_targets(makefile)

    assert "continued-gate" in reachable
    assert "repeated-gate" in reachable
    assert "multi-target-gate" in reachable
    assert "disabled-gate" not in reachable
    assert "recipe-only-gate" not in reachable


@pytest.mark.parametrize(
    ("assignment", "reference"),
    [
        ("GATES := hidden-gate", "$(GATES)"),
        ("GATES := hidden-gate", "${GATES}"),
        ("G := hidden-gate", "$G"),
    ],
)
def test_reachability_expands_variable_prerequisites(assignment: str, reference: str) -> None:
    makefile = "\n".join(
        [
            assignment,
            f"check: {reference}",
            "ci: visible-gate",
            "hidden-gate:",
            "visible-gate:",
        ]
    )

    assert "hidden-gate" in _reachable_targets(makefile)


def test_reachability_observes_active_conditional_rules() -> None:
    makefile = "ifeq (1, 0)\ncheck: disabled-gate\nendif\ncheck: visible-gate\nci: visible-gate\nvisible-gate:"

    reachable = _reachable_targets(makefile)

    assert "visible-gate" in reachable
    assert "disabled-gate" not in reachable


@pytest.mark.parametrize("prefix", ["", "private ", "override ", "export "])
def test_reachability_excludes_target_specific_variable_values(prefix: str) -> None:
    makefile = "\n".join(
        [
            "check: visible-gate",
            f"check: {prefix}GATES = disabled-gate",
            "ci: visible-gate",
            "visible-gate:",
        ]
    )

    reachable = _reachable_targets(makefile)

    assert "visible-gate" in reachable
    assert "disabled-gate" not in reachable


def test_reverse_wiki_guard_rejects_fabricated_gate_without_exemptions() -> None:
    makefile = "check: live-gate\nci: live-gate\nlive-gate:"
    wiki = "`make live-gate`\n`make fabricated-gate`\n"

    assert _stale_wiki_gates(wiki, makefile) == ["fabricated-gate"]


def test_the_wiki_names_every_gate_the_blocking_lanes_run() -> None:
    wiki = WIKI.read_text(encoding="utf-8")

    undocumented = sorted(target for target in _gate_targets() if target not in wiki)

    assert undocumented == [], (
        "wiki/Validation-and-CI.md publishes the repo-native validation commands but does not name "
        "these gates, which `make check` or `make ci` runs and which can fail a contributor's "
        f"build: {undocumented}. See issue #227."
    )


def test_the_wiki_names_no_gate_the_blocking_lanes_have_stopped_running() -> None:
    """The reverse direction, which is the one that misleads.

    The check above fails when a gate is undocumented. It says nothing when a gate is REMOVED from
    the blocking lanes and its wiki entry stays - leaving the page claiming a control that no
    longer runs.

    A missing entry understates coverage and someone eventually notices. A stale entry OVERSTATES
    it and reads exactly like a live one. That is the same direction as a documented threshold
    looser than the enforced one (lotus-performance#476, `969` published against an enforced `879`)
    and the looser-than-enforced maxima on lotus-gateway#665: it misleads toward believing a
    control exists.

    Scoped to `*-gate` / `*-gates` names so it reads only what it can attribute; prose mentioning a
    gate in passing is not an entry, and this test does not try to judge prose.

    Matches the bidirectional form landed in lotus-render#76 - the two repositories publish the
    same kind of page and should not guard it differently.
    """

    wiki = WIKI.read_text(encoding="utf-8")
    live = _gate_targets()

    named_in_wiki = {match.group(1) for match in _WIKI_GATE_NAME.finditer(wiki)}

    # The guard the first version omitted, and the reason it failed open. `_gate_targets`
    # already asserts its own set is non-empty; the wiki-derived set had no such check, so the
    # one side whose input format can change underneath it was the one side left unguarded.
    assert named_in_wiki, (
        "No gate names were found in the wiki page. Either the page stopped naming gates - "
        "which the forward check would also catch - or this pattern stopped matching how they "
        "are written, in which case this check asserts nothing. Both are failures."
    )

    stale = sorted(name for name in named_in_wiki if name not in live)

    assert stale == [], (
        "The wiki names these gates, but no blocking lane in the Makefile runs them any more. A "
        "wiki entry outliving its gate claims a control that does not exist, which is the "
        f"direction that misleads: {stale}. Remove the entry or restore the gate."
    )
