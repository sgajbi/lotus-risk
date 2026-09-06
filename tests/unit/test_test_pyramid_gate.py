"""Hold the pyramid gate and its `governance` marker honest.

The gate deselects `pytest.mark.governance` so it measures the *product's* test shape. That makes
the marker load-bearing in two directions, and both need holding:

- If the marker is under-applied, governance tests inflate the unit bucket and squeeze the
  integration and e2e ratios, which is the defect issue #220 records: the repository was two unit
  tests away from being unable to add any CI-contract coverage without turning CI red.
- If it is over-applied, product tests vanish from the denominator and the gate stops governing
  anything. Nothing here can detect that automatically, which is why the marker is explicit and
  reviewed rather than inferred.

The completeness check below covers `tests/unit` only. A `tests/unit` module that never imports
product code cannot be testing product behaviour, so the signal is sound there. It is deliberately
not applied to `tests/integration` or `tests/e2e`, where exercising the service over HTTP without
importing it is the normal shape - `tests/integration/test_concentration_live_characterization.py`
is a product test by that route, and an automatic rule would mismark it.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "test_pyramid_gate.py"

MARKER_NAME = "governance"
PRODUCT_PACKAGE = "app"


def _is_governance_mark(node: ast.expr) -> bool:
    """Match `pytest.mark.governance` as an expression, not as text."""

    return (
        isinstance(node, ast.Attribute)
        and node.attr == MARKER_NAME
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    )


def _declares_governance_marker(module: Path) -> bool:
    """Whether pytest will actually apply the marker, not whether the text appears.

    A substring search over the source passes when the marker text sits in a comment, a docstring
    or an unrelated string constant, so a module that merely *mentions* the marker would satisfy
    the completeness guard while pytest never deselects it. It also rejects valid forms: an
    annotated assignment, or a list of markers.

    Reading the module-level `pytestmark` binding from the AST answers the question that matters:
    is this module actually marked.
    """

    tree = ast.parse(module.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            targets: list[ast.expr] = [node.target]
        elif isinstance(node, ast.Assign):
            targets = list(node.targets)
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets):
            continue
        value = node.value
        if value is None:
            continue
        candidates = list(value.elts) if isinstance(value, ast.List | ast.Tuple) else [value]
        if any(_is_governance_mark(candidate) for candidate in candidates):
            return True
    return False


def _imports_product_code(module: Path) -> bool:
    for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == PRODUCT_PACKAGE for alias in node.names):
                return True
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.split(".")[0] == PRODUCT_PACKAGE
        ):
            return True
    return False


#: Modules lifted BYTE-IDENTICALLY from a canonical implementation in another
#: repository. They carry no in-file marker on purpose: editing one to add this
#: repository's convention would fork an estate-wide control and silently stop
#: it receiving canonical fixes, which is how a sibling's copy of this same
#: checker fell 102 lines behind. `tests/unit/conftest.py` marks them at
#: collection time instead, so the pyramid accounting is identical while the
#: file stays comparable to its canonical blob.
#: Retires when the module is no longer a verbatim lift.
CANONICAL_LIFTS = {"tests/unit/test_branch_protection_policy.py"}


def test_unit_modules_that_never_touch_product_code_declare_the_marker() -> None:
    unmarked = [
        path
        for module in sorted((ROOT / "tests" / "unit").rglob("test_*.py"))
        if (path := module.relative_to(ROOT).as_posix()) not in CANONICAL_LIFTS
        and not _imports_product_code(module)
        and not _declares_governance_marker(module)
    ]

    assert unmarked == [], (
        "These unit modules never import product code, so they are not product tests, but they do "
        f"not bind `pytestmark` to `pytest.mark.{MARKER_NAME}`. They will be counted in the "
        f"product pyramid and squeeze the integration and e2e ratios: {unmarked}. See issue #220."
    )


def test_every_canonical_lift_is_marked_at_collection_time() -> None:
    """The exemption above must not become a hole: a module exempt from the
    in-file marker still has to BE marked, or it lands in the product
    pyramid exactly as an unmarked module would.

    This collects each lift through pytest itself and asserts the marker is
    APPLIED. Searching conftest text would not do: its own docstring names
    both the module and the marker, so a grep-based check passes even with
    `pytest_collection_modifyitems` deleted - the failure mode this test
    exists to catch.
    """

    for lift in sorted(CANONICAL_LIFTS):
        collected = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                lift,
                "--collect-only",
                "-q",
                "-m",
                MARKER_NAME,
                "--no-header",
                "-p",
                "no:cacheprovider",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert collected.returncode == 0, collected.stdout + collected.stderr
        selected = [line for line in collected.stdout.splitlines() if line.startswith(f"{lift}::")]
        assert selected, (
            f"{lift} is exempt from the in-file marker, but collecting it under "
            f"`-m {MARKER_NAME}` selects nothing - so nothing marks it and it counts as a "
            f"product test: {collected.stdout}"
        )
