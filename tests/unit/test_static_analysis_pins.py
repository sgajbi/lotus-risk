"""Tools whose OUTPUT is the gate must be pinned, not floored.

A floored linter changes the gate's verdict without anybody changing the repository. `ruff>=0.15.0`
resolved to 0.16.4 in CI while the local virtualenv held 0.15.21, so `make lint` passed locally and
found 237 errors in CI on the same commit — see issue #218.

Type stubs count. `pandas-stubs` floated from 3.0.3.260530 to 3.0.5.260730 and mypy produced five
errors in `src/app/services/risk/helpers.py:73` — unchanged code, changed verdict, exactly like a
new lint rule. Stubs are the analyser's rule set for third-party APIs.

Because a stub release tracks its runtime, `pandas` and `numpy` are pinned alongside: a pinned stub
against a floating runtime is worse than either, since mypy would then check against an API the
installed package does not have.

Coverage tooling counts, and its failure mode is the more dangerous one. `--cov-fail-under` compares
a produced number against a fixed threshold (`COVERAGE_FAIL_UNDER ?= 98`). Which branches count,
which files are included and how partial branches are treated have all changed across coverage
majors — so an upgrade can move what `98` means with no commit, and it can move it in the
*permissive* direction: measure fewer branches, the percentage rises, the gate passes more easily,
and nothing reports that the bar moved. A floored linter fails loudly; a floored coverage tool can
fail silently and in our favour.

Test runners are deliberately *not* covered. A `pytest` upgrade does not invent new assertions about
this codebase. The nearest counter-example is `pytest-asyncio`, whose `asyncio_mode` default could
silently skip unmarked async tests — but all 61 async tests here carry an explicit
`@pytest.mark.asyncio`, so they are marker-protected rather than mode-dependent. The line is
therefore *output of the gate* versus *runner of the code*, not linters versus everything else.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
PRE_COMMIT_CONFIG = ROOT / ".pre-commit-config.yaml"

# Tools whose output is the gate: a release can change the verdict with no commit.
GATE_OUTPUT_TOOLS = frozenset(
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
        # These produce the number --cov-fail-under compares against a fixed threshold.
        "coverage",
        "pytest-cov",
        # `make security-audit` consumes its pass/fail, and a release can change which advisories
        # are reported or how resolution works - the ruff scenario exactly. Its advisory database is
        # fetched at runtime, so pinning the tool does not freeze what it knows about; a pinned
        # pip-audit still learns about new CVEs. The usual objection to pinning a security tool
        # therefore does not apply here, because currency lives in the data, not in the pin.
        "pip-audit",
    }
)

# Deliberately NOT pinned, recorded so it reads as considered rather than missed:
#
#   pre-commit  orchestrates hooks; it does not produce the gate's verdict. The hooks it runs are
#               pinned by .pre-commit-config.yaml revisions, which is where reproducibility actually
#               lives. Pinning the runner would add churn without adding determinism.
#   pytest,     a runner upgrade does not invent new assertions about this codebase. The nearest
#   pytest-     counter-example is pytest-asyncio's asyncio_mode default, which could silently skip
#   asyncio     unmarked async tests - but all 61 async tests here carry an explicit
#               @pytest.mark.asyncio, so they are marker-protected rather than mode-dependent.
DELIBERATELY_FLOORED = frozenset({"pre-commit", "pytest", "pytest-asyncio"})

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


def test_every_gate_output_tool_is_pinned_to_an_exact_version() -> None:
    requirements = _dev_requirements()

    missing = sorted(GATE_OUTPUT_TOOLS - set(requirements))
    assert missing == [], f"Declared gate-output tools not found in dev extras: {missing}"

    floored = sorted(
        f"{name}{requirements[name]}"
        for name in GATE_OUTPUT_TOOLS
        if not requirements[name].startswith("==")
    )
    assert floored == [], (
        "These gate-output tools are floored rather than pinned, so a new release changes the "
        f"gate's verdict with no commit: {floored}. See issue #218."
    )


def test_the_pinned_versions_are_the_ones_actually_installed() -> None:
    """A pin nobody installs is a pin that has not been tested."""

    from importlib import metadata

    requirements = _dev_requirements()
    mismatched = []
    for name in sorted(GATE_OUTPUT_TOOLS):
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


def test_ruff_pre_commit_hook_matches_the_package_pin() -> None:
    pinned = _dev_requirements()["ruff"].removeprefix("==").strip()
    config = PRE_COMMIT_CONFIG.read_text(encoding="utf-8")
    ruff_block = re.search(
        r"repo: https://github\.com/astral-sh/ruff-pre-commit\s+rev: v(?P<version>[^\s]+)",
        config,
    )

    assert ruff_block is not None, "The governed Ruff pre-commit hook is missing."
    assert ruff_block.group("version") == pinned, (
        "The Ruff pre-commit hook and installed gate package differ, so contributors and CI "
        f"enforce different rule sets: hook={ruff_block.group('version')}, package={pinned}."
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


def test_deliberately_floored_tools_are_still_floored() -> None:
    """A decision not to pin must stay a decision, not decay into an accident.

    If one of these is later pinned without removing it from `DELIBERATELY_FLOORED`, the recorded
    reasoning and the manifest disagree, and the next reader cannot tell which is current.
    """

    requirements = _dev_requirements()

    contradicted = sorted(
        f"{name}{requirements[name]}"
        for name in DELIBERATELY_FLOORED
        if name in requirements and requirements[name].startswith("==")
    )
    assert contradicted == [], (
        "These tools are pinned but recorded as deliberately floored, so the manifest and the "
        f"reasoning above disagree: {contradicted}. Move them into GATE_OUTPUT_TOOLS with a reason."
    )


def test_every_dev_tool_is_either_pinned_or_explicitly_dispositioned() -> None:
    """No third category. A tool nobody classified is a tool nobody decided about.

    This is what stops the list going stale: adding a dev dependency forces a choice between
    `GATE_OUTPUT_TOOLS` and `DELIBERATELY_FLOORED`, rather than silently landing in neither.
    """

    classified = GATE_OUTPUT_TOOLS | DELIBERATELY_FLOORED
    unclassified = sorted(set(_dev_requirements()) - classified)

    assert unclassified == [], (
        "These dev dependencies are neither declared gate-output tools nor recorded as deliberately "
        f"floored: {unclassified}. Classify each one - see issue #218."
    )
