"""The pre-commit mypy hook must refuse an environment that is not CI's.

The hook runs mypy through whatever interpreter is on `PATH` -- which is what
makes it the same checker CI runs, and also what lets a commit from an
unactivated shell run a different one.

This repository's `mypy.ini` is `strict = True` over `src, tests` with no
`ignore_missing_imports`, so a wrong environment fails loudly on its own: 586
errors, 266 of them `import-not-found`. The guard's job here is therefore not
to prevent a silent pass -- it is to replace those 586 cascading errors with
one sentence naming the interpreter and what is missing, so a contributor fixes
their environment instead of concluding the hook is broken and reaching for
`--no-verify`.

The guard's value is entirely in what it refuses, so that is what these assert
-- and the acceptance path is asserted too, because a suite written only from
negative cases passes just as happily against a guard that refuses everything.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

#: This exercises the contributor toolchain, not product behaviour, so it
#: must not be counted in the product test pyramid and squeeze the
#: integration and e2e ratios (#220).
pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts import run_typecheck_hook as hook


def test_the_real_environment_is_accepted() -> None:
    assert hook._problems() == []


def test_an_interpreter_below_requires_python_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hook, "_minimum_python", lambda project: (99, 0))

    problems = hook._problems()

    assert len(problems) == 1
    assert "older than the required 99.0" in problems[0]


def test_a_mypy_other_than_the_pin_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A different mypy reports different diagnostics on the same tree.

    That is why `pyproject.toml` pins it exactly, and why having *some* mypy
    installed does not make this the checker CI runs.
    """

    monkeypatch.setattr(hook, "_pinned_mypy", lambda project: "0.0.1")

    problems = hook._problems()

    assert len(problems) == 1
    assert "pyproject.toml pins 0.0.1" in problems[0]


def test_losing_the_pin_is_refused_rather_than_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A guard that quietly passes when its input disappears is not a guard."""

    monkeypatch.setattr(hook, "_pinned_mypy", lambda project: None)

    problems = hook._problems()

    assert len(problems) == 1
    assert "no longer pins an exact mypy version" in problems[0]


def test_a_missing_declared_dependency_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from packaging.requirements import Requirement

    declared = hook._runtime_requirements
    monkeypatch.setattr(
        hook,
        "_runtime_requirements",
        lambda project: [*declared(project), Requirement("a-package-no-environment-has")],
    )

    problems = hook._problems()

    assert len(problems) == 1
    assert "a-package-no-environment-has" in problems[0]


def test_losing_the_dependency_list_is_refused_rather_than_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(hook, "_runtime_requirements", lambda project: [])

    problems = hook._problems()

    assert len(problems) == 1
    assert "declares no runtime dependencies" in problems[0]


def test_every_declared_runtime_dependency_is_checked() -> None:
    """The set checked is the set declared, not a copy someone maintains.

    A dependency added to `pyproject.toml` extends this check automatically. A
    hand-written list would omit one eventually, and the omission would be
    invisible until an environment was missing exactly that package.
    """

    project = hook._project()
    declared = {
        requirement.split("[")[0].split(">")[0].split("=")[0].split("<")[0].strip()
        for requirement in project["dependencies"]
    }

    assert {r.name for r in hook._runtime_requirements(project)} == declared


@pytest.mark.parametrize(
    "spelling",
    [
        "mypy==2.3.0",
        "mypy == 2.3.0",
        'mypy==2.3.0 ; python_version >= "3.12"',
        "mypy[faster-cache]==2.3.0",
        "MyPy==2.3.0",
    ],
)
def test_every_pep508_spelling_of_the_same_pin_is_read(spelling: str) -> None:
    """The pin must be found however it is legally written.

    Each spelling this missed would return None, which the guard reads as "the
    project stopped pinning mypy" and refuses -- so reformatting the
    requirement would block every commit, blaming a file that had not changed.
    """

    assert hook._pinned_mypy({"dependencies": [spelling]}) == "2.3.0"


@pytest.mark.parametrize("spelling", ["mypy>=2.3.0", "mypy", "mypy<3", "mypy!=2.0"])
def test_a_requirement_that_is_not_an_exact_pin_is_not_read_as_one(spelling: str) -> None:
    assert hook._pinned_mypy({"dependencies": [spelling]}) is None


def test_a_pin_whose_marker_is_false_here_is_not_the_pin_in_force() -> None:
    """An entry pip would not select is not the pin this environment must match."""

    assert hook._pinned_mypy({"dependencies": ['mypy==9.9.9 ; python_version < "3"']}) is None


@pytest.mark.parametrize(
    ("declaration", "expected"),
    [
        (">=3.12", (3, 12)),
        (">=3.12.7", (3, 12, 7)),  # a patch floor must not truncate to (3, 12)
        (">=3.12,<4.0", (3, 12)),
        ("==3.12.*", None),  # a valid specifier, not a version to compare against
        ("", None),
    ],
)
def test_requires_python_is_read_from_the_specifier(
    declaration: str, expected: tuple[int, ...] | None
) -> None:
    assert hook._minimum_python({"requires-python": declaration}) == expected


def test_a_stale_pinned_stub_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stub version changes what mypy reports on unchanged code.

    This repository pins `pandas-stubs` for exactly that reason: floating it
    from 3.0.3.260530 to 3.0.5.260730 changed mypy's findings. An environment
    with the correct mypy and a stale stub is therefore not the environment CI
    type-checks in -- and it is the harder case to notice, because everything
    the earlier checks look at is right.
    """

    pins = {**hook._analyzer_pins(hook._project()), "pandas-stubs": "3.0.5.260730"}

    problems = _problems_with_pins(monkeypatch, pins)

    assert len(problems) == 1
    assert "pandas-stubs" in problems[0]
    assert "changes mypy's findings" in problems[0]


def test_a_pinned_stub_that_is_absent_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    problems = _problems_with_pins(
        monkeypatch, {**hook._analyzer_pins(hook._project()), "types-absent": "1.0.0"}
    )

    assert len(problems) == 1
    assert "types-absent is not installed" in problems[0]


def test_the_analyzer_pins_are_derived_not_listed() -> None:
    """mypy plus anything named as a stub, by the packaging convention.

    Derived so a stub added to `pyproject.toml` is covered without a second
    edit here -- a hand-written list is the shape that silently omits one.
    """

    pins = hook._analyzer_pins(
        {
            "optional-dependencies": {
                "dev": [
                    "mypy==2.3.0",
                    "pandas-stubs==3.0.3.260530",
                    "types-requests==2.0.0",
                    "ruff==0.16.4",  # a tool, not an analysis input
                    "pytest>=9.0.0",  # not an exact pin
                ]
            }
        }
    )

    assert pins == {
        "mypy": "2.3.0",
        "pandas-stubs": "3.0.3.260530",
        "types-requests": "2.0.0",
    }


def test_the_guard_refuses_without_packaging_instead_of_crashing() -> None:
    """The guard runs in the environment it exists to diagnose.

    `packaging` is a dev dependency, not stdlib, so a bare interpreter -- the
    exact case being refused -- raised `ModuleNotFoundError` at import time and
    printed a traceback where the actionable message belonged. Run as a
    subprocess with `-S`, because the failure is at import and cannot be
    observed from inside an already-imported module.
    """

    completed = subprocess.run(
        [sys.executable, "-S", str(ROOT / "scripts" / "run_typecheck_hook.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,  # a non-zero exit is the assertion, not an error
    )

    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    assert "packaging" in completed.stderr
    assert "--no-verify" in completed.stderr


def _problems_with_pins(monkeypatch: pytest.MonkeyPatch, pins: dict[str, str]) -> list[str]:
    """`_problems()` with the analyzer pins replaced for one test."""

    monkeypatch.setattr(hook, "_analyzer_pins", lambda project: pins)
    return hook._problems()


@pytest.mark.parametrize(
    ("requirement", "fragment"),
    [
        ("numpy==9.9.9", "numpy"),  # the exact-pin case: a stale runtime after a pull
        ("fastapi>=99.0.0", "fastapi"),  # a floor the installed version does not meet
    ],
)
def test_an_installed_version_outside_the_declared_range_is_refused(
    monkeypatch: pytest.MonkeyPatch, requirement: str, fragment: str
) -> None:
    """Presence is not the question -- mypy checks against installed type information.

    `numpy` is pinned exactly. A contributor who pulls a change to that pin and
    does not reinstall has every distribution present and the wrong one of them,
    which a presence-only check accepts while mypy silently checks against a
    different API than CI.
    """

    from packaging.requirements import Requirement

    monkeypatch.setattr(hook, "_runtime_requirements", lambda project: [Requirement(requirement)])

    problems = hook._problems()

    assert len(problems) == 1
    assert fragment in problems[0]
    assert "different type information" in problems[0]


def test_the_guard_refuses_without_tomllib_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`tomllib` is standard library only from Python 3.11.

    An older system interpreter is one of the cases this guard exists to
    diagnose, and importing `tomllib` at module level crashed before the
    refusal could be printed -- the same defect as the `packaging` import one
    line above it, which I had fixed while leaving this one.

    Exercised by setting the flag the import sets, because this environment has
    no 3.10 interpreter to run. That proves the branch, the exit status and the
    message. It does not prove behaviour on a real 3.10, and the distinction is
    worth keeping rather than implying more than was run.
    """

    monkeypatch.setattr(hook, "_TOML_MISSING", True)

    exit_code = hook.main()

    stderr = capsys.readouterr().err
    assert exit_code == 1
    assert "tomllib" in stderr
    assert "3.11" in stderr
    assert "--no-verify" in stderr


def test_the_guard_refuses_without_packaging_by_the_same_route(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The two preconditions are answered in order, each without the other."""

    monkeypatch.setattr(hook, "_PARSER_MISSING", True)

    exit_code = hook.main()

    stderr = capsys.readouterr().err
    assert exit_code == 1
    assert "packaging" in stderr


def test_the_test_framework_is_required_when_mypy_analyses_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`mypy.ini` is `files = src, tests`, and the tests import pytest 95 times.

    Those imports are analysis inputs exactly as the runtime ones are. Without
    the framework installed, a strict run emits the same `import-not-found`
    cascade this guard exists to replace -- after reporting the environment as
    fine, because the runtime dependencies were all present.
    """

    from packaging.requirements import Requirement

    monkeypatch.setattr(hook, "_runtime_requirements", lambda project: [])
    monkeypatch.setattr(
        hook, "_test_framework_requirements", lambda project: [Requirement("pytest-absent>=1.0")]
    )

    problems = hook._problems()

    assert any("pytest-absent" in problem for problem in problems)


def test_the_framework_requirement_follows_mypy_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read from `mypy.ini`, not assumed.

    If `tests` is dropped from `files`, the framework stops being an analysis
    input and must stop being demanded -- otherwise the guard enforces a
    configuration the project no longer has.
    """

    monkeypatch.setattr(hook, "_mypy_analyses_tests", lambda: False)

    assert hook._test_framework_requirements(hook._project()) == []


def test_the_framework_set_is_derived_from_the_naming_convention() -> None:
    """pytest and its plugins, not a hand-written list, and not every dev tool.

    `bandit`, `radon` and `vulture` are dev dependencies mypy never sees.
    Demanding them would refuse environments that are correct for this hook.
    """

    project = {
        "optional-dependencies": {
            "dev": [
                "pytest>=9.0.0",
                "pytest-asyncio>=1.2.0",
                "bandit==1.9.4",
                "radon==6.0.1",
            ]
        }
    }

    names = {requirement.name for requirement in hook._test_framework_requirements(project)}

    assert names == {"pytest", "pytest-asyncio"}


def test_the_analysed_tree_really_does_import_the_framework() -> None:
    """The premise, checked rather than asserted.

    If the tests stopped importing pytest, demanding it would be enforcing a
    dependency nothing needs -- so the claim that makes this check meaningful
    is worth pinning to the tree it describes.
    """

    import ast

    importers = 0
    for path in (ROOT / "tests").rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name == "pytest" for a in node.names):
                importers += 1
                break
            if isinstance(node, ast.ImportFrom) and node.module == "pytest":
                importers += 1
                break

    assert importers > 50, "the tests no longer import pytest; this check's premise has moved"
