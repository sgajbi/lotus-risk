"""Static-analysis tools must be pinned, not floored.

A floored linter changes the gate's verdict without anybody changing the repository. `ruff>=0.15.0`
resolved to 0.16.4 in CI while the local virtualenv held 0.15.21, so `make lint` passed locally and
found 237 errors in CI on the same commit — see issue #218.

Test runners are deliberately *not* covered. A pytest upgrade does not invent new assertions about
our code; a linter upgrade invents new findings about code nobody touched. That is the distinction
this check encodes.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"

# Tools whose rule set is the gate: a release can turn `main` red with no commit.
STATIC_ANALYSIS_TOOLS = frozenset(
    {
        "ruff",
        "mypy",
        "bandit",
        "deptry",
        "import-linter",
        "radon",
        "vulture",
    }
)

_REQUIREMENT = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)\s*(?P<spec>.*)$")


def _dev_requirements() -> dict[str, str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    requirements: dict[str, str] = {}
    for raw in data["project"]["optional-dependencies"]["dev"]:
        match = _REQUIREMENT.match(raw.strip())
        assert match is not None, f"Unparseable dev requirement: {raw!r}"
        requirements[match.group("name").lower()] = match.group("spec").strip()
    return requirements


def test_every_static_analysis_tool_is_pinned_to_an_exact_version() -> None:
    requirements = _dev_requirements()

    missing = sorted(STATIC_ANALYSIS_TOOLS - set(requirements))
    assert missing == [], f"Declared static-analysis tools not found in dev extras: {missing}"

    floored = sorted(
        f"{name}{requirements[name]}"
        for name in STATIC_ANALYSIS_TOOLS
        if not requirements[name].startswith("==")
    )
    assert floored == [], (
        "These static-analysis tools are floored rather than pinned, so a new release changes the "
        f"gate's verdict with no commit: {floored}. See issue #218."
    )


def test_the_pinned_versions_are_the_ones_actually_installed() -> None:
    """A pin nobody installs is a pin that has not been tested."""

    import importlib.metadata as metadata

    requirements = _dev_requirements()
    mismatched = []
    for name in sorted(STATIC_ANALYSIS_TOOLS):
        pinned = requirements[name].removeprefix("==").strip()
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:  # pragma: no cover - tool absent locally
            continue
        if installed != pinned:
            mismatched.append(f"{name}: pinned {pinned}, installed {installed}")

    assert mismatched == [], (
        "The pinned version differs from what this environment runs, so local validation is not "
        f"evidence about CI: {mismatched}"
    )
