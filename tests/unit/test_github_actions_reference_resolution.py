"""Every action reference in every workflow must be a *well-formed, pinned* reference.

    This is a FORM check, not a resolvability check, and the distinction matters. It rejects a
    bare version like `0.32.0`, which cannot resolve, and a mutable branch like `main`, which
    resolves but is unpinned. It accepts `aquasecurity/trivy-action@v9.99.0` - well-formed,
    pinned, and nonexistent. A deleted or renamed `v`-tag still fails at `Set up job` and
    nothing here sees it.

    Saying otherwise would be the failure mode this repository keeps finding: a name asserting a
    property the code does not have, in the place people look for the guarantee. Full
    resolution against the registry needs the network and belongs in a scheduled check - filed
    separately - not in pre-push validation.

`image-release.yml` referenced `aquasecurity/trivy-action@0.32.0`. That tag does not exist - the
publisher tags with a `v` prefix - so the job failed at `Set up job` before a single step ran,
taking the image build, SBOM, vulnerability scan, SARIF upload, cosign signature and provenance
attestation with it.

It survived from 2026-07-05 to 2026-08-26 because the workflow had **never been triggered**: merges
were performed by `github-actions[bot]` under `github.token`, which GitHub does not treat as an
eligible `push` trigger. Two independent defects, and the first hid the second completely. See
issues #227 and #216.

The check is deliberately offline and syntactic rather than a registry lookup. A gate that needs the
network fails for reasons unrelated to the repository, and would not run in the pre-push validation
where this belongs.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

sys.path.insert(0, str(ROOT))

from scripts.validate_github_actions_runtime import (
    ANY_ACTION_USE_PATTERN,
    RESOLVABLE_REF_PATTERN,
)


def _all_references() -> list[tuple[str, int, str, str]]:
    found = []
    for path in sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")]):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = ANY_ACTION_USE_PATTERN.search(line)
            if match is not None:
                found.append((path.name, number, match.group("slug"), match.group("ref")))
    return found


def test_the_matcher_finds_the_references_that_are_actually_there() -> None:
    """A matcher that finds nothing would make every check below vacuously pass."""

    references = _all_references()

    assert len(references) >= 10, f"Only {len(references)} action references found: {references}"
    slugs = {slug for _, _, slug, _ in references}
    for expected in ("actions/checkout", "aquasecurity/trivy-action", "sigstore/cosign-installer"):
        assert expected in slugs, f"{expected} not matched; slugs seen: {sorted(slugs)}"


def test_every_action_reference_is_a_pinned_well_formed_ref() -> None:
    malformed = [
        f"{name}:{number}: {slug}@{ref}"
        for name, number, slug, ref in _all_references()
        if not RESOLVABLE_REF_PATTERN.fullmatch(ref)
    ]

    assert malformed == [], (
        "These action references are neither a `v`-prefixed tag nor a commit SHA. A bare version "
        "cannot resolve at all; a branch resolves but is unpinned, so the action can change "
        f"under the workflow with no commit: {malformed}. See issue #227."
    )


@pytest.mark.parametrize(
    ("ref", "resolvable"),
    [
        ("v0.36.0", True),
        ("v6", True),
        ("v3.1.2-beta", True),
        ("a" * 40, True),
        ("0.32.0", False),
        ("1.0", False),
        ("main", False),
        ("latest", False),
        ("a" * 39, False),
    ],
)
def test_the_reference_form_rule_accepts_and_rejects_the_right_shapes(
    ref: str, resolvable: bool
) -> None:
    assert bool(RESOLVABLE_REF_PATTERN.fullmatch(ref)) is resolvable, ref


def test_the_gate_fails_on_an_unresolvable_reference(tmp_path: Path) -> None:
    """Run the gate itself, not just its regex - the wiring is what CI executes."""

    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "broken.yml").write_text(
        "jobs:"
        + chr(10)
        + "  a:"
        + chr(10)
        + "    steps:"
        + chr(10)
        + "      - uses: aquasecurity/trivy-action@0.32.0"
        + chr(10),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate_github_actions_runtime.py"),
            "--workflows-dir",
            str(workflows),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "0.32.0" in completed.stderr


def test_the_trivy_reference_matches_the_sibling_that_demonstrably_works() -> None:
    """lotus-archive runs `v0.36.0` in a lane that succeeds; adopt it rather than a nearby number."""

    release = (WORKFLOWS / "image-release.yml").read_text(encoding="utf-8")

    match = re.search(r"aquasecurity/trivy-action@(\S+)", release)
    assert match is not None, "The vulnerability scan no longer references trivy-action."
    assert match.group(1) == "v0.36.0", match.group(1)


def test_the_form_check_accepts_a_well_formed_reference_that_does_not_exist() -> None:
    """Pins the limit of this guard so nobody reads it as more than it is.

    `v9.99.0` is a `v`-prefixed tag and passes. It does not exist. A deleted or renamed tag behaves
    the same way, and the job would still fail at `Set up job` - which is the class this guard does
    NOT close. Recorded as a passing assertion rather than a comment, so the boundary is checked
    rather than described.
    """

    assert RESOLVABLE_REF_PATTERN.fullmatch("v9.99.0") is not None
    assert RESOLVABLE_REF_PATTERN.fullmatch("v0.0.0-does-not-exist") is not None
