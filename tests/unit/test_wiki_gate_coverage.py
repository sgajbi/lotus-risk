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


def test_the_wiki_names_every_gate_the_blocking_lanes_run() -> None:
    wiki = WIKI.read_text(encoding="utf-8")

    undocumented = sorted(target for target in _gate_targets() if target not in wiki)

    assert undocumented == [], (
        "wiki/Validation-and-CI.md publishes the repo-native validation commands but does not name "
        "these gates, which `make check` or `make ci` runs and which can fail a contributor's "
        f"build: {undocumented}. See issue #227."
    )
