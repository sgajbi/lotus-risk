"""Static-analysis tools, and the stubs they read, must be pinned, not floored.

A floored linter changes the gate's verdict without anybody changing the repository. `ruff>=0.15.0`
resolved to 0.16.4 in CI while the local virtualenv held 0.15.21, so `make lint` passed locally and
found 237 errors in CI on the same commit — see issue #218.

Type stubs count. `pandas-stubs` floated from 3.0.3.260530 to 3.0.5.260730 and mypy produced five
errors in `src/app/services/risk/helpers.py:73` — unchanged code, changed verdict, exactly like a
new lint rule. Stubs are the analyser's rule set for third-party APIs.

Because a stub release tracks its runtime, `pandas` and `numpy` are pinned alongside: a pinned stub
against a floating runtime is worse than either, since mypy would then check against an API the
installed package does not have.

Test runners are deliberately *not* covered. A pytest upgrade does not invent new assertions about
our code; a linter or stub upgrade invents new findings about code nobody touched. That is the
distinction this check encodes.
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
        # A stub release changes what mypy concludes about unchanged code.
        "pandas-stubs",
    }
)

# Runtimes whose stubs are pinned above. Pinning the stub while the runtime floats would let mypy
# check against an API the installed package does not have.
STUBBED_RUNTIMES = frozenset({"pandas", "numpy"})

_REQUIREMENT = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)\s*(?P<spec>.*)$")


def _dev_requirements() -> dict[str, str]:
    return _requirements(
        tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["optional-dependencies"][
            "dev"
        ]
    )


def _runtime_requirements() -> dict[str, str]:
    return _requirements(
        tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    )


def _requirements(raw_requirements: list[str]) -> dict[str, str]:
    requirements: dict[str, str] = {}
    for raw in raw_requirements:
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


def test_runtimes_whose_stubs_are_pinned_are_pinned_too() -> None:
    """A pinned stub against a floating runtime checks an API that may not be installed."""

    requirements = _runtime_requirements()

    floored = sorted(
        f"{name}{requirements[name]}"
        for name in STUBBED_RUNTIMES
        if name in requirements and not requirements[name].startswith("==")
    )
    assert floored == [], (
        "These runtimes have pinned stubs but floating versions, so mypy can be checking against "
        f"an API the installed package does not have: {floored}. See issue #218."
    )


def test_the_pandas_stub_tracks_the_pinned_pandas() -> None:
    """`pandas-stubs` versions are `<pandas version>.<stub date>`; a mismatch is a silent drift."""

    stub = _dev_requirements()["pandas-stubs"].removeprefix("==").strip()
    pandas = _runtime_requirements()["pandas"].removeprefix("==").strip()

    assert stub.startswith(f"{pandas}."), (
        f"pandas-stubs {stub} does not track pandas {pandas}; mypy would be reading stubs for a "
        "different release of the library that is actually installed."
    )
