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


def _targets_in(lane: str) -> list[str]:
    match = re.search(rf"^{lane}: (.+)$", MAKEFILE.read_text(encoding="utf-8"), re.M)
    assert match is not None, f"The {lane} lane is missing from the Makefile."
    return match.group(1).split()


def _is_gate(target: str) -> bool:
    return target.endswith("-gate") or target.endswith("-gates")


def _gate_targets() -> set[str]:
    """Every `*-gate` target reachable from the blocking lanes, including aggregate members."""

    makefile = MAKEFILE.read_text(encoding="utf-8")
    reachable: set[str] = set()
    for lane in ("check", "ci"):
        for target in _targets_in(lane):
            if not _is_gate(target):
                continue
            reachable.add(target)
            aggregate = re.search(rf"^{re.escape(target)}: (.+)$", makefile, re.M)
            if aggregate:
                reachable.update(m for m in aggregate.group(1).split() if _is_gate(m))
    assert reachable, (
        "No gate targets found in the blocking lanes; this check would assert nothing."
    )
    return reachable


# Gate names as the wiki actually writes them: inside backticks, usually behind `make `. The
# first version omitted the optional `make ` prefix and so matched NOTHING - 0 of 13 backticked
# gate spellings on this page - which made the reverse check pass for every possible page
# content, including an injected `make totally-fictional-gate`. See lotus-render#77.
_WIKI_GATE_NAME = re.compile(r"`(?:make\s+)?([a-z0-9]+(?:-[a-z0-9]+)*-gates?)`")

# Targets the wiki documents as standalone conveniences that no blocking lane invokes by name.
# `domain-data-product-gate` is an alias for `domain-product-validate`, which `check` and `ci`
# both run via `mesh-contract-validate` - so the validation is enforced and only the NAME is
# absent from any failing build. The wiki entry says so explicitly; this allowance exists so
# that statement is asserted rather than assumed, and a new entry cannot join it silently.
DOCUMENTED_ALIASES = frozenset({"domain-data-product-gate"})


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
