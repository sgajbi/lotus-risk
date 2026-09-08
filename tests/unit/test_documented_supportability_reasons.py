"""The wiki's reason list is derived from the alias, not maintained beside it.

`wiki/API-Surface.md` publishes the supportability reason vocabulary to
consumers. It was a **fourth** hand-maintained copy of `RiskSupportabilityReason`
-- after the alias itself, `_SUPPORTABILITY_REASON_PRECEDENCE` (#281) and the
Glossary -- and it drifted the moment #283 added
`group_return_series_unavailable`: the code returned the new reason on **every**
attribution response while the published surface still listed nine.

Nothing failed. A consumer reading the documentation would not know the value
exists, and would have no reason to look.

This is the same defect this repository fixed twice in code this cycle, one
layer out. The fix is the same too: derive the requirement from the alias and
let a drifted copy fail here, rather than restating it and hoping.

Documentation drift is worth a test precisely because it has no other detector.
A wrong constant breaks something eventually; a wrong document is read by a
person who then acts on it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from app.contracts.risk import RiskSupportabilityReason

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
API_SURFACE = ROOT / "wiki" / "API-Surface.md"
GLOSSARY = ROOT / "wiki" / "Glossary.md"

DECLARED = frozenset(get_args(RiskSupportabilityReason))


def _reason_row_codes() -> frozenset[str]:
    """The `| reason | ... |` row of the supportability table, as a set."""
    text = API_SURFACE.read_text(encoding="utf-8")
    row = re.search(r"^\|\s*reason\s*\|(.+?)\|\s*$", text, re.MULTILINE)
    assert row, "wiki/API-Surface.md has no `| reason | ... |` row"
    return frozenset(re.findall(r"`([a-z_]+)`", row.group(1)))


def test_the_published_reason_row_lists_every_declared_reason() -> None:
    """The direction that drifted: code gained a reason, the surface did not.

    A consumer builds against the documentation. A reason returned on every
    response and absent from the published list is a value they cannot plan for
    and will meet in production.
    """
    missing = sorted(DECLARED - _reason_row_codes())

    assert not missing, (
        f"{missing} are returned by the service and absent from wiki/API-Surface.md's reason row"
    )


def test_the_published_row_invents_no_reason() -> None:
    """The other direction, which is worse for being plausible.

    A documented code the service never emits sends a consumer to handle a case
    that cannot occur, and there is nothing in the code to contradict it.
    """
    invented = sorted(_reason_row_codes() - DECLARED)

    assert not invented, f"{invented} are documented in wiki/API-Surface.md and never emitted"


def test_the_glossary_explains_the_reasons_it_mentions() -> None:
    """The Glossary is selective by design, so it is checked for honesty, not coverage.

    It explains the reasons a reader is most likely to meet rather than all of
    them, which is right for a glossary. What it must not do is explain a code
    that does not exist -- so this asserts the subset relation, not equality.
    """
    mentioned = frozenset(re.findall(r"\*\*`([a-z_]+)`\*\*", GLOSSARY.read_text(encoding="utf-8")))

    # Intersected with DECLARED-adjacent names, NOT with `_reason_row_codes()`.
    # The two tests above force the row to equal DECLARED, so
    # `(mentioned & _reason_row_codes()) - DECLARED` is empty by construction and
    # could never fail -- a reason deleted from the alias and the row but left in
    # the Glossary would have passed. Reported by review; the assertion related
    # two things already constrained equal, which is the shape that always holds.
    #
    # The Glossary also explains state and freshness values, so a bare
    # `mentioned - DECLARED` would flag `ready`, `blocked` and the rest. The
    # discriminator is the reason-code suffix set this vocabulary uses.
    reason_shaped = {
        name
        for name in mentioned
        if name.endswith(("_observations", "_unavailable", "_issue", "_complete", "_mode"))
    }
    stale = sorted(reason_shaped - DECLARED)
    assert not stale, (
        f"{stale} read as supportability reasons in the Glossary and are not in "
        "RiskSupportabilityReason"
    )


def test_group_return_series_unavailable_is_documented_as_unconditional() -> None:
    """The property a consumer most needs and would not infer from a code name.

    It is returned on every attribution response, including unflagged ones --
    the case most likely to be presented as empirical. A reader who assumes it
    appears only on degraded-looking output will activate a surface on a weight
    proxy, which is what `lotus-report#254` and `lotus-render#270` are gated on.
    """
    text = API_SURFACE.read_text(encoding="utf-8")
    assert "group_return_series_unavailable" in text, "the reason is not documented at all"

    # The paragraph that explains it, not a fixed window after the first
    # mention: the first mention is the table row, and the prose sits below the
    # rest of the table. An offset-based check passed or failed on where the
    # table happened to end.
    blank_line = "\n" + "\n"
    paragraphs = [p for p in text.split(blank_line) if "group_return_series_unavailable" in p]
    explanatory = [p for p in paragraphs if not p.lstrip().startswith("|")]
    assert explanatory, "the reason appears only in a table row, with no prose explaining it"

    # The PHRASE, not the word. The same paragraph already contains "every group
    # is fed the same portfolio-level return", so a bare `"every" in p` is
    # satisfied by an unrelated sentence and passes while the claim under test
    # has been deleted -- measured, not hypothesised: removing "**every**
    # attribution response" left this assertion green.
    # Emphasis stripped first: the source says "**every** attribution response",
    # so matching the raw text fails on the asterisks while the claim is present
    # and correct. A content assertion should not depend on markdown styling.
    plain = [p.lower().replace("*", "") for p in explanatory]
    assert any("every attribution response that produced a decomposition" in p for p in plain), (
        "the surface must scope this reason to responses that produced a decomposition: "
        "a bare 'every attribution response' is false, because an empty result returns "
        "no_return_observations without reaching the decomposition"
    )


def test_the_empty_response_exception_is_documented() -> None:
    """The claim I first published was unconditional, and it was wrong.

    `supportability_from_attribution_results` returns early when the period
    assessment is `empty`, carrying `no_return_observations` -- so the
    group-return limitation is **not** on every attribution response. Reported by
    review after I had documented the stronger claim and written a test that
    pinned it.

    Documenting the exception matters more than the general case: a reader who
    believes the reason is unconditional will treat its absence as a bug, and go
    looking for a fault in a response that is behaving correctly.
    """
    text = API_SURFACE.read_text(encoding="utf-8").lower().replace("*", "")

    assert "no_return_observations" in text
    window = text.split("group_return_series_unavailable")[-1]
    assert "empty" in window and "no_return_observations" in window, (
        "the surface must say which response does NOT carry this reason, and why"
    )
