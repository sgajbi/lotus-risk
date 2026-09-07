"""`quality/` is classified, and the classification agrees with the code (#279).

The original framing of #279 was "fourteen committed artifacts make conflicts a
function of PR count", with an implied remedy of deleting generated files. Both
halves were wrong: one-PR-per-repo already removed the conflict pressure, and the
fourteen are not one category. Deciding by extension or by count would have swept
authored records in with regenerated reports.

So the remedy is a classification -- and a classification nobody checks is a
comment. These tests hold `quality/README.md` to the code:

  * every file in `quality/` is classified, so a new one cannot arrive unlabelled;
  * the generator's write targets are *parsed from the generator* and must equal
    the files labelled generated, so the label cannot drift from behaviour;
  * no authored file is a write target, which is the specific harm -- a generated
    report silently overwriting a human decision;
  * every authored file has a reader, so a file retained out of habit is
    reclassified rather than kept because it is already there.

The last one earns its place: #279 notes that a "retained baseline" with no
consumer is just a stale number with authority.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
QUALITY_DIR = ROOT / "quality"
README = QUALITY_DIR / "README.md"
GENERATOR = ROOT / "scripts" / "generate_quality_baseline.py"

#: `(QUALITY_DIR / "name.md").write_text(...)` -- the generator's own write sites.
_WRITE_TARGET = re.compile(r'QUALITY_DIR\s*/\s*"([^"]+)"\s*\)\s*\.write_text')
_TABLE_FILE = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)
_SECTION = re.compile(r"^## (.+)$", re.MULTILINE)


def _section(title_fragment: str) -> str:
    text = README.read_text(encoding="utf-8")
    starts = [(match.start(), match.group(1)) for match in _SECTION.finditer(text)]
    for index, (start, title) in enumerate(starts):
        if title_fragment.lower() in title.lower():
            end = starts[index + 1][0] if index + 1 < len(starts) else len(text)
            return text[start:end]
    raise AssertionError(f"quality/README.md has no section matching {title_fragment!r}")


def _classified(title_fragment: str) -> set[str]:
    return set(_TABLE_FILE.findall(_section(title_fragment)))


def _present() -> set[str]:
    return {
        path.name for path in QUALITY_DIR.iterdir() if path.is_file() and path.name != "README.md"
    }


def _write_targets() -> set[str]:
    return set(_WRITE_TARGET.findall(GENERATOR.read_text(encoding="utf-8")))


def test_every_file_is_classified() -> None:
    """A file arriving here without a label is the thing that starts the drift."""
    classified = _classified("Authored records") | _classified("Generated measurements")

    unclassified = sorted(_present() - classified)
    assert not unclassified, (
        f"{unclassified} are in quality/ but not classified in quality/README.md; "
        "label each authored or generated before committing it"
    )


def test_the_classification_names_no_missing_file() -> None:
    """The other direction: a label for a file that was deleted."""
    classified = _classified("Authored records") | _classified("Generated measurements")

    missing = sorted(classified - _present())
    assert not missing, f"quality/README.md classifies {missing}, which are not present"


def test_the_generated_label_matches_what_the_generator_writes() -> None:
    """Parsed from the generator, not restated beside it.

    A hand-kept list of generated files is a second opinion that cannot usefully
    disagree with the first. This reads the `write_text` sites out of
    `generate_quality_baseline.py`, so adding a write target without labelling it
    fails here rather than after the file is overwritten.
    """
    assert _write_targets() == _classified("Generated measurements")


def test_the_generator_writes_over_no_authored_file() -> None:
    """The specific harm, asserted directly rather than implied by the two sets.

    #279's acceptance asks that `generate_quality_baseline.py` be checked for
    whether it can write over an authored file. It cannot, and this is the check
    -- stated as its own test so the reason survives, rather than being a
    consequence of the equality above that a later refactor could quietly drop.
    """
    overwritten = sorted(_write_targets() & _classified("Authored records"))

    assert not overwritten, (
        f"generate_quality_baseline.py writes {overwritten}, which quality/README.md "
        "records as authored; a generated report must not overwrite a human decision"
    )


@pytest.mark.parametrize("authored", sorted(_classified("Authored records")))
def test_every_authored_file_has_a_reader(authored: str) -> None:
    """A retained file with no consumer is a stale number with authority.

    Parameterised over the classification, so a file added to the authored table
    has to name something that reads it. The reader is asserted to exist rather
    than merely be named: the README's second column is a path, and a path that
    does not resolve documents a relationship that is not there.
    """
    row = re.search(
        rf"^\|\s*`{re.escape(authored)}`\s*\|(.+?)\|\s*$",
        _section("Authored records"),
        re.MULTILINE,
    )
    assert row, f"{authored} has no reader recorded in quality/README.md"

    referenced = re.findall(r"`([^`]+\.(?:py|md|json))`", row.group(1))
    assert referenced, f"{authored}'s reader column names no file"

    resolved = [name for name in referenced if (ROOT / name).exists()]
    assert resolved, f"{authored} names readers {referenced}, none of which exist"
