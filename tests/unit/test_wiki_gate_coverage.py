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

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
WIKI = ROOT / "wiki" / "Validation-and-CI.md"


def _targets_in(lane: str, makefile: str) -> list[str]:
    match = re.search(rf"^{lane}: (.+)$", makefile, re.M)
    assert match is not None, f"The {lane} lane is missing from the Makefile."
    return match.group(1).split()


def _is_gate(target: str) -> bool:
    return target.endswith("-gate") or target.endswith("-gates")


def _target_dependencies(makefile: str) -> dict[str, list[str]]:
    dependencies: dict[str, list[str]] = {}
    for match in re.finditer(r"^([a-zA-Z0-9_-]+):\s*(.*)$", makefile, re.M):
        prerequisites = match.group(2).partition(";")[0].split()
        dependencies.setdefault(match.group(1), []).extend(prerequisites)
    return dependencies


def _reachable_targets(makefile: str) -> set[str]:
    dependencies = _target_dependencies(makefile)
    pending = [target for lane in ("check", "ci") for target in _targets_in(lane, makefile)]
    reachable: set[str] = set()
    while pending:
        target = pending.pop()
        if target in reachable:
            continue
        reachable.add(target)
        pending.extend(dependencies.get(target, []))
    return reachable


def _targets_with_recipes(makefile: str) -> set[str]:
    targets: set[str] = set()
    current_target: str | None = None
    for line in makefile.splitlines():
        target_match = re.match(r"^([a-zA-Z0-9_-]+):\s*(.*)$", line)
        if target_match:
            current_target = target_match.group(1)
            if ";" in target_match.group(2):
                targets.add(current_target)
            continue
        if line.startswith("\t") and line.strip() and current_target is not None:
            targets.add(current_target)
    return targets


def _targets_with_continued_prerequisites(makefile: str) -> set[str]:
    return {
        match.group(1) for match in re.finditer(r"^([a-zA-Z0-9_-]+):[^\n]*\\\s*$", makefile, re.M)
    }


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

# Standalone convenience aliases documented in the wiki but not invoked by a blocking lane. Empty
# is the preferred state; any future exemption must prove that it is a real target whose complete
# prerequisite work is reachable from `check` or `ci`.
DOCUMENTED_ALIASES: frozenset[str] = frozenset()


def _invalid_documented_aliases(aliases: frozenset[str], makefile: str) -> list[str]:
    dependencies = _target_dependencies(makefile)
    reachable = _reachable_targets(makefile)
    targets_with_recipes = _targets_with_recipes(makefile)
    targets_with_continued_prerequisites = _targets_with_continued_prerequisites(makefile)
    invalid: list[str] = []
    for alias in sorted(aliases):
        if alias not in dependencies:
            invalid.append(f"{alias} (not a Makefile target)")
            continue
        if alias in targets_with_recipes:
            invalid.append(f"{alias} (contains recipe commands)")
            continue
        if alias in targets_with_continued_prerequisites:
            invalid.append(f"{alias} (uses continued prerequisites)")
            continue
        unreachable = sorted(set(dependencies[alias]) - reachable)
        if not dependencies[alias] or unreachable:
            invalid.append(f"{alias} (unreachable prerequisites: {unreachable})")
    return invalid


def test_documented_alias_exemptions_are_real_and_reachable() -> None:
    invalid = _invalid_documented_aliases(
        DOCUMENTED_ALIASES,
        MAKEFILE.read_text(encoding="utf-8"),
    )

    assert invalid == [], f"Documented gate aliases do not prove blocking work: {invalid}"


def test_documented_alias_guard_rejects_fabricated_and_unreachable_names() -> None:
    makefile = "\n".join(
        [
            "check: live-gate",
            "ci: live-gate",
            "live-gate: live-validation",
            "inline-recipe-alias: live-validation ; python inline_check.py",
            "orphan-gate: orphan-validation",
            "recipe-alias: live-validation",
            "\tpython recipe_check.py",
            "repeated-alias: hidden-validation",
            "repeated-alias: live-validation",
            "continued-alias: live-validation \\",
            " hidden-validation",
        ]
    )

    invalid = _invalid_documented_aliases(
        frozenset(
            {
                "fabricated-gate",
                "continued-alias",
                "inline-recipe-alias",
                "orphan-gate",
                "recipe-alias",
                "repeated-alias",
            }
        ),
        makefile,
    )

    assert invalid == [
        "continued-alias (uses continued prerequisites)",
        "fabricated-gate (not a Makefile target)",
        "inline-recipe-alias (contains recipe commands)",
        "orphan-gate (unreachable prerequisites: ['orphan-validation'])",
        "recipe-alias (contains recipe commands)",
        "repeated-alias (unreachable prerequisites: ['hidden-validation'])",
    ]


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

    stale = sorted(
        name for name in named_in_wiki if name not in live and name not in DOCUMENTED_ALIASES
    )

    assert stale == [], (
        "The wiki names these gates, but no blocking lane in the Makefile runs them any more. A "
        "wiki entry outliving its gate claims a control that does not exist, which is the "
        f"direction that misleads: {stale}. Remove the entry or restore the gate."
    )
