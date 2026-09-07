"""Run this project's mypy from the pre-commit hook, or refuse and say why.

`mirrors-mypy` resolves the hook into an isolated environment holding mypy and
nothing else. This repository's `mypy.ini` is `strict = True` over `src, tests`
with **no** `ignore_missing_imports`, so that environment cannot resolve
`fastapi`, `pydantic`, `numpy` or `pandas` and the hook fails on every commit.
Measured on an unchanged tree:

    make typecheck (project mypy 2.3.0)  ->  Success: no issues found in 385 files
    pre-commit run mypy --all-files      ->  Found 586 errors in 233 files

266 of those are `import-not-found` and the rest largely follow from them. A
contributor meets that on their first commit, and a hook that fails for
everyone is one that gets skipped with `--no-verify` rather than fixed.

Matching the hook's `rev` to the pinned version would not help: the version was
never the problem, the missing dependency graph was. Listing the graph in
`additional_dependencies` would be a hand-maintained second copy of
`pyproject.toml` that drifts silently.

So the hook runs the project's own mypy, which makes it the same checker CI
runs by construction rather than by comparison. That means it depends on the
project environment being active, and this script refuses clearly when it is
not.

**How that refusal differs here from `lotus-report`.** Report sets
`ignore_missing_imports`, so a wrong interpreter there reports
`Success: no issues found` having resolved everything to `Any` -- a silent
pass, and the guard prevents it. This repository has no such setting, so a
wrong interpreter fails loudly on its own. The guard's value here is narrower
and worth stating honestly: it replaces 586 cascading import errors with one
sentence naming the interpreter and what is missing, so the contributor fixes
their environment instead of concluding the hook is broken.
"""

from __future__ import annotations

import importlib.metadata
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

# Imported defensively, because this guard runs in the environment it exists to
# diagnose. `packaging` is a project dev dependency, not stdlib, so a bare or
# unactivated interpreter -- exactly the case being refused -- would otherwise
# raise ModuleNotFoundError at import time and print a traceback instead of the
# actionable message. Reproducible with `python -S scripts/run_typecheck_hook.py`.
try:
    from packaging.requirements import InvalidRequirement, Requirement
    from packaging.specifiers import InvalidSpecifier, SpecifierSet
    from packaging.utils import canonicalize_name
    from packaging.version import InvalidVersion, Version

    _PARSER_MISSING = False
except ModuleNotFoundError:  # pragma: no cover - exercised by a subprocess test
    _PARSER_MISSING = True

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"


def _project() -> dict[str, Any]:
    with PYPROJECT.open("rb") as handle:
        return cast(dict[str, Any], tomllib.load(handle)["project"])


def _runtime_distributions(project: dict[str, Any]) -> list[str]:
    """The runtime dependencies `pyproject.toml` declares, as distribution names.

    Derived rather than listed, so a dependency added there extends this check
    without a second edit and cannot be silently omitted from it.
    """

    names = []
    for entry in project.get("dependencies", []):
        try:
            names.append(Requirement(entry).name)
        except InvalidRequirement:
            continue
    return names


def _pinned_mypy(project: dict[str, Any]) -> str | None:
    """The exact mypy version this project pins, or None if it stops pinning one.

    Parsed with `packaging` rather than a regex: PEP 508 permits whitespace
    around the operator, environment markers and extras, and a hand-rolled
    expression matches one spelling of several. Every spelling it missed would
    return None, which this guard reads as "the project stopped pinning mypy"
    and refuses -- so a maintainer reformatting the requirement would block
    every commit, blaming a file that had not changed.

    A requirement whose marker is false for this interpreter is skipped: it is
    not installed here, so its specifier is not the pin in force.
    """

    groups: list[list[str]] = [list(project.get("dependencies", []))]
    groups.extend(list(entries) for entries in project.get("optional-dependencies", {}).values())
    for entry in (entry for group in groups for entry in group):
        try:
            requirement = Requirement(entry)
        except InvalidRequirement:
            continue
        if canonicalize_name(requirement.name) != "mypy":
            continue
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        specifiers = list(requirement.specifier)
        if len(specifiers) == 1 and specifiers[0].operator == "==":
            return str(specifiers[0].version)
    return None


def _minimum_python(project: dict[str, Any]) -> tuple[int, ...] | None:
    """The lower bound `requires-python` states, or None if it states none.

    The whole release tuple is kept: a `>=3.12.7` floor truncated to (3, 12)
    would accept 3.12.0 through 3.12.6, which do not satisfy the metadata.
    """

    try:
        specifiers = SpecifierSet(str(project.get("requires-python", "")))
    except InvalidSpecifier:
        return None
    versions = []
    for specifier in specifiers:
        if specifier.operator not in (">=", "==", "~="):
            continue
        try:
            versions.append(Version(specifier.version))
        except InvalidVersion:
            # `==3.12.*` is a valid specifier but not a valid version. A
            # wildcard names a series, not a floor to compare against.
            continue
    if not versions:
        return None
    return tuple(max(versions).release)


def _analyzer_pins(project: dict[str, Any]) -> dict[str, str]:
    """Exactly-pinned dev dependencies that change what mypy reports.

    mypy itself, plus type stubs. Stubs are identified by the packaging naming
    convention -- a `-stubs` suffix or a `types-` prefix -- rather than by a
    hand-written list, so a stub added to `pyproject.toml` is covered without a
    second edit here.

    Stubs belong in this check because they are analysis inputs, not tooling
    around it. This repository pins `pandas-stubs` for exactly that reason:
    floating it from 3.0.3.260530 to 3.0.5.260730 changed mypy's findings on
    unchanged code. An environment with the right mypy and a stale stub is not
    the environment CI type-checks in, and the hook would disagree with CI
    while appearing correct.
    """

    pins: dict[str, str] = {}
    for entries in project.get("optional-dependencies", {}).values():
        for entry in entries:
            try:
                requirement = Requirement(entry)
            except InvalidRequirement:
                continue
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            name = canonicalize_name(requirement.name)
            if not (name == "mypy" or name.endswith("-stubs") or name.startswith("types-")):
                continue
            specifiers = list(requirement.specifier)
            if len(specifiers) == 1 and specifiers[0].operator == "==":
                pins[requirement.name] = str(specifiers[0].version)
    return pins


def _is_installed(distribution: str) -> bool:
    try:
        importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return False
    return True


def _problems() -> list[str]:
    project = _project()
    problems: list[str] = []

    minimum = _minimum_python(project)
    if minimum is not None and sys.version_info[: len(minimum)] < minimum:
        running = ".".join(str(part) for part in sys.version_info[:3])
        problems.append(
            f"Python {running} is older than the required {'.'.join(str(part) for part in minimum)}"
        )

    pinned = _pinned_mypy(project)
    if pinned is None:
        problems.append("pyproject.toml no longer pins an exact mypy version for this to check")
    else:
        try:
            installed = importlib.metadata.version("mypy")
        except importlib.metadata.PackageNotFoundError:
            problems.append(f"mypy is not installed (pyproject.toml pins {pinned})")
        else:
            if installed != pinned:
                problems.append(f"mypy {installed} is installed, but pyproject.toml pins {pinned}")

    for distribution, pinned_version in sorted(_analyzer_pins(project).items()):
        if canonicalize_name(distribution) == "mypy":
            continue  # already compared above, with its own message
        try:
            installed_version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            problems.append(
                f"{distribution} is not installed (pyproject.toml pins {pinned_version}), "
                "and it changes what mypy reports"
            )
        else:
            if installed_version != pinned_version:
                problems.append(
                    f"{distribution} {installed_version} is installed, but pyproject.toml pins "
                    f"{pinned_version}; a stub version changes mypy's findings on unchanged code"
                )

    declared = _runtime_distributions(project)
    if not declared:
        problems.append("pyproject.toml declares no runtime dependencies for this to check")
    missing = [name for name in declared if not _is_installed(name)]
    if missing:
        problems.append(
            "these declared dependencies are absent, so a strict run would report "
            f"hundreds of import-not-found errors rather than real findings: {', '.join(missing)}"
        )

    return problems


def main() -> int:
    if _PARSER_MISSING:
        # Answered before anything that needs a parser. This is the strongest
        # possible signal that the environment is wrong -- `packaging` is a
        # declared dev dependency, so its absence means the project was not
        # installed here at all.
        print(
            "This is not the environment CI type-checks in: the project is not "
            "installed here at all.",
            file=sys.stderr,
        )
        print(f"  interpreter : {sys.executable}", file=sys.stderr)
        print(
            "  - `packaging` is missing, and it is a declared dev dependency of this project",
            file=sys.stderr,
        )
        print(
            "Activate the project environment and commit again. Do not use --no-verify: "
            "the check being skipped is the one CI will run.",
            file=sys.stderr,
        )
        return 1

    problems = _problems()
    if problems:
        print(
            "This is not the environment CI type-checks in, so its verdict would not "
            "mean what the hook claims.",
            file=sys.stderr,
        )
        print(f"  interpreter : {sys.executable}", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "Activate the project environment and commit again. Do not use --no-verify: "
            "the check being skipped is the one CI will run.",
            file=sys.stderr,
        )
        return 1

    return subprocess.call([sys.executable, "-m", "mypy", "--config-file", "mypy.ini"])


if __name__ == "__main__":
    raise SystemExit(main())
